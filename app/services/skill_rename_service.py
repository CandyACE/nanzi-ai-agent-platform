"""技能重命名：目录改名 + 引用同步。

技能 ID 就是目录名，因此「重命名」在磁盘上是一次 ``os.rename``；真正麻烦的是
**引用**——同一个 ID 散落在三处：

* ``skill_publications.source_personal_skill_id``：个人技能的发布谱系（删源判定、
  重复提交复用、下架能力都依赖它）；
* ``agents.skills``：智能体自定义公共技能白名单（JSON 列表）；
* Redis 的会话资源范围 ``conversation:<uid>:<cid>:resource_scope_v1`` 里的
  ``skills`` 列表（用户挂载的技能 chip，TTL 30 天）。

只改目录不碰这三处，会得到「技能还在但哪都挂不上、发布记录变成孤儿」的静默断链，
比不支持重命名更糟。所以这里统一处理，并把同步结果如实回报给调用方。
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

#: 技能 ID 白名单（与端点层一致：字母/数字/下划线/连字符，1-128）
SKILL_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,128}$")

#: 与 /skills 下更早注册的字面路由同名的 ID 会被遮蔽，禁止使用
RESERVED_SKILL_IDS = frozenset(
    {"personal", "stats", "bindings", "publication-requests", "import", "export"}
)

#: 单次重命名最多同步的会话数（Redis 会话范围），防止把低频管理操作做成全库扫描
MAX_SESSION_SYNC = 2000


class SkillRenameError(ValueError):
    """重命名被拒绝（ID 非法、目标已存在、源不存在等）。"""


def validate_new_skill_id(new_skill_id: str) -> str:
    """校验新技能 ID，返回去空白后的合法值。"""
    candidate = str(new_skill_id or "").strip()
    if not candidate:
        raise SkillRenameError("缺少新的技能 ID")
    if not SKILL_ID_PATTERN.match(candidate):
        raise SkillRenameError("技能 ID 仅允许字母、数字、下划线与连字符，长度 1-128")
    if candidate.lower() in RESERVED_SKILL_IDS:
        raise SkillRenameError(f"技能 ID {candidate} 是平台保留标识，请换一个")
    return candidate


async def sync_publication_lineage(
    session: AsyncSession, *, old_skill_id: str, new_skill_id: str
) -> int:
    """把发布谱系里的来源个人技能 ID 改为新 ID，返回受影响记录数。"""
    from app.models.skill_publication import SkillPublication

    result = await session.execute(
        select(SkillPublication).where(
            SkillPublication.source_personal_skill_id == old_skill_id
        )
    )
    publications = list(result.scalars().all())
    for publication in publications:
        publication.source_personal_skill_id = new_skill_id
    if publications:
        await session.commit()
    return len(publications)


async def sync_agent_bindings(
    session: AsyncSession, *, old_skill_id: str, new_skill_id: str
) -> List[str]:
    """把智能体自定义技能白名单（``agents.skills``）里的旧 ID 改为新 ID。

    返回被改动的智能体 ID 列表。注意必须**整体赋一个新列表**：JSON 列的原地修改
    SQLAlchemy 不会标记为脏数据，直接 ``append``/下标赋值会被静默丢弃。
    """
    from app.models.agent import Agent

    result = await session.execute(select(Agent).where(Agent.skills.isnot(None)))
    changed: List[str] = []
    for agent in result.scalars().all():
        skills = agent.skills
        if not isinstance(skills, list):
            continue
        if old_skill_id not in skills:
            continue
        agent.skills = [new_skill_id if item == old_skill_id else item for item in skills]
        changed.append(str(getattr(agent, "id", "")))
    if changed:
        await session.commit()
    return changed


async def sync_conversation_mounts(*, old_skill_id: str, new_skill_id: str) -> int:
    """把 Redis 里各会话挂载的技能 ID 改为新 ID，返回被改动的会话数。

    尽力而为：Redis 不可用或个别 key 解析失败都不应让重命名整体失败——目录已经改好，
    会话里的旧引用最多表现为「重新选一次技能」。
    """
    from app.services.conversation_resource_service import ConversationResourceService

    try:
        from app.core.redis import get_redis

        redis = await get_redis()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[SkillRename] Redis 不可用，跳过会话挂载同步: %s", exc)
        return 0
    if not redis:
        return 0

    suffix = ConversationResourceService.SUFFIX
    pattern = f"{ConversationResourceService.KEY_PREFIX}:*:*:{suffix}"
    updated = 0
    cursor = 0
    try:
        while True:
            cursor, keys = await redis.scan(cursor=cursor, match=pattern, count=200)
            for key in keys:
                raw = await redis.get(key)
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")
                try:
                    scope = json.loads(raw or "{}")
                except (TypeError, ValueError):
                    continue
                skills = scope.get("skills")
                if not isinstance(skills, list):
                    continue
                hit = False
                for item in skills:
                    if isinstance(item, dict) and item.get("id") == old_skill_id:
                        item["id"] = new_skill_id
                        hit = True
                if not hit:
                    continue
                await redis.set(key, json.dumps(scope, ensure_ascii=False))
                updated += 1
                if updated >= MAX_SESSION_SYNC:
                    logger.warning(
                        "[SkillRename] 会话挂载同步达到上限 %s，其余会话请用户手动重选技能",
                        MAX_SESSION_SYNC,
                    )
                    return updated
            if cursor == 0:
                break
    except Exception as exc:  # noqa: BLE001
        logger.warning("[SkillRename] 会话挂载同步中断（已同步 %s 个）: %s", updated, exc)
    return updated


def rename_skill_directory(current_dir: str, *, new_skill_id: str) -> str:
    """把技能目录改名为 ``new_skill_id``，返回新目录绝对路径。

    ``os.rename`` 在同一文件系统内是原子的：失败时原目录原样保留，不会出现「半个技能」。
    目标已存在时明确拒绝，而不是覆盖——覆盖会直接毁掉另一个技能。
    """
    current_dir = os.path.abspath(current_dir)
    if not os.path.isdir(current_dir):
        raise SkillRenameError("技能不存在")
    parent = os.path.dirname(current_dir)
    target_dir = os.path.join(parent, new_skill_id)
    if os.path.abspath(target_dir) == current_dir:
        raise SkillRenameError("新技能 ID 与当前 ID 相同")
    if os.path.exists(target_dir):
        raise SkillRenameError(f"技能 ID {new_skill_id} 已被占用，请换一个")
    if not os.path.isfile(os.path.join(current_dir, "SKILL.md")):
        # 目录不是技能（可能是个残留目录/软链接），改名它没有意义
        raise SkillRenameError("目标目录不是有效的技能目录（缺少 SKILL.md）")
    try:
        os.rename(current_dir, target_dir)
    except OSError as exc:
        raise SkillRenameError(f"目录改名失败：{exc}") from exc
    return target_dir


async def rename_skill(
    session: AsyncSession,
    *,
    current_dir: str,
    old_skill_id: str,
    new_skill_id: str,
    scope: str,
) -> Dict[str, Any]:
    """执行完整重命名并返回同步报告。

    顺序刻意如此：**先把目录改好**（这是用户真正要的结果，且原子），再尽力同步各处引用。
    引用同步失败不回滚目录改名——否则用户会看到「什么都没发生」，而技能其实完全可用，
    只是个别会话需要重新挂载。
    """
    new_skill_id = validate_new_skill_id(new_skill_id)
    if new_skill_id == old_skill_id:
        raise SkillRenameError("新技能 ID 与当前 ID 相同")

    new_dir = rename_skill_directory(current_dir, new_skill_id=new_skill_id)
    report: Dict[str, Any] = {
        "skill_id": new_skill_id,
        "previous_skill_id": old_skill_id,
        "scope": scope,
        "directory": new_dir,
        "synced": {},
        "warnings": [],
    }

    if scope == "personal":
        try:
            count = await sync_publication_lineage(
                session, old_skill_id=old_skill_id, new_skill_id=new_skill_id
            )
            report["synced"]["publications"] = count
        except Exception as exc:  # noqa: BLE001
            logger.warning("[SkillRename] 发布谱系同步失败: %s", exc)
            report["warnings"].append("发布记录中的来源技能 ID 未能同步，请人工核对发布列表")
    else:
        try:
            agents = await sync_agent_bindings(
                session, old_skill_id=old_skill_id, new_skill_id=new_skill_id
            )
            report["synced"]["agents"] = agents
        except Exception as exc:  # noqa: BLE001
            logger.warning("[SkillRename] 智能体绑定同步失败: %s", exc)
            report["warnings"].append("部分智能体的技能白名单未能同步，请在智能体配置里重新勾选")

    sessions = await sync_conversation_mounts(
        old_skill_id=old_skill_id, new_skill_id=new_skill_id
    )
    report["synced"]["conversations"] = sessions
    return report


def cleanup_empty_parent(path: str) -> None:
    """尽力清理残留的空目录（导入回滚后可能出现），失败忽略。"""
    try:
        if os.path.isdir(path) and not os.listdir(path):
            shutil.rmtree(path, ignore_errors=True)
    except OSError:  # pragma: no cover - 仅日志
        logger.debug("[SkillRename] 清理空目录失败: %s", path)


__all__ = [
    "MAX_SESSION_SYNC",
    "RESERVED_SKILL_IDS",
    "SKILL_ID_PATTERN",
    "SkillRenameError",
    "cleanup_empty_parent",
    "rename_skill",
    "rename_skill_directory",
    "sync_agent_bindings",
    "sync_conversation_mounts",
    "sync_publication_lineage",
    "validate_new_skill_id",
]
