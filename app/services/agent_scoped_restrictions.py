"""智能体级可限制资源的候选构建。

「功能限制」弹框要回答的问题是：**这个智能体本身绑定了什么**，管理员才能在其上做排除。
因此候选不是"平台全部资源"，而是该智能体当前版本的绑定集合：

- 内置工具 / 自定义 API 工具：``AIAgentVersion.tools`` 里的非 MCP 项；
- MCP：``AIAgentVersion.tools`` 里的 ``mcp-<server_id>:<tool_name>``，按 server 分组展示；
- 公共技能：``AIAgentVersion.skills``（本版本的公共技能白名单）；
- 个人技能：当前用户的私人技能目录。

落库的 ``resource_id`` 一律用**与全局禁用同一套标识**：
- 工具用纯工具名（MCP 也用 ``tool_name``，与 ``forbidden-catalog`` 的候选 id 一致），
  这样运行时 ``to_runtime_tool_names`` 那套别名/运行时名匹配可以直接复用，不必为
  "智能体级"再造一套匹配语义；
- 技能用技能 id。

``forbidden_globally`` 用于让弹框把全局已禁项置灰只读——排除机制只增不减，不允许在
智能体层面"放开"全局禁用，否则两层语义会互相打架。
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import AIAgent, AIAgentVersion
from app.models.mcp import McpToolCache
from app.models.tool import SysApiTool

logger = logging.getLogger(__name__)

MCP_TOOL_PREFIX = "mcp-"


def _as_list(raw: Any) -> List[str]:
    """``tools`` / ``skills`` 是 JSON 列，历史数据可能是字符串、None 或已解析的列表。"""
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw or "[]")
        except Exception:
            return []
    if isinstance(raw, (list, tuple)):
        return [str(item).strip() for item in raw if str(item).strip()]
    return []


def split_agent_tool_bindings(tools: Any) -> tuple[List[str], List[tuple[str, str]]]:
    """把 ``AIAgentVersion.tools`` 拆成（普通工具名, [(server_id, tool_name)]）。

    MCP 项的真实形态是 ``mcp-<server_id>:<tool_name>``（见线上数据）。这里解析出
    ``tool_name`` 作为落库标识、``server_id`` 用于分组展示。
    """
    plain: List[str] = []
    mcp_pairs: List[tuple[str, str]] = []
    for entry in _as_list(tools):
        if entry.startswith(MCP_TOOL_PREFIX) and ":" in entry:
            server_id, _, tool_name = entry[len(MCP_TOOL_PREFIX):].partition(":")
            server_id, tool_name = server_id.strip(), tool_name.strip()
            if server_id and tool_name:
                mcp_pairs.append((server_id, tool_name))
                continue
        plain.append(entry)
    return plain, mcp_pairs


async def _latest_version(db: AsyncSession, agent_id: str) -> Optional[AIAgentVersion]:
    """取该智能体**最新**版本（优先已发布）。

    限制挂在 agent 维度而不是版本维度（产品口径），但候选清单必须来自某个具体版本。
    取最新已发布版本；若从未发布则退回最新版本，避免"草稿智能体无法配置限制"。
    """
    base = select(AIAgentVersion).where(AIAgentVersion.agent_id == agent_id)
    published = (
        await db.execute(
            base.where(AIAgentVersion.status == "PUBLISHED").order_by(
                AIAgentVersion.version_number.desc()
            ).limit(1)
        )
    ).scalar_one_or_none()
    if published is not None:
        return published
    return (
        await db.execute(
            base.order_by(AIAgentVersion.version_number.desc()).limit(1)
        )
    ).scalar_one_or_none()


async def build_restrictable_resources(
    db: AsyncSession,
    *,
    agent_id: str,
    globally_forbidden_tools: Optional[set[str]] = None,
    globally_forbidden_skills: Optional[set[str]] = None,
    personal_skills: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """构建某智能体的可限制资源分组。

    ``globally_forbidden_*`` 与 ``personal_skills`` 由调用方传入（调用方已有用户上下文），
    这样本函数只依赖 ``db`` 与 agent_id，便于单测。
    """
    globally_forbidden_tools = globally_forbidden_tools or set()
    globally_forbidden_skills = globally_forbidden_skills or set()

    agent = await db.get(AIAgent, agent_id)
    if agent is None:
        raise ValueError(f"agent not found: {agent_id}")

    version = await _latest_version(db, agent_id)
    plain_tools, mcp_pairs = split_agent_tool_bindings(
        version.tools if version is not None else None
    )
    # 技能候选的范围由 ``skills_custom`` 决定（不是由 skills 是否为空决定）：
    # ``agent_manager`` 里注明 skills_custom=False 时运行时**使用全部公共技能**，
    # 此时若只列 version.skills（通常是空），管理员就没有任何技能可以限制，
    # 而那些技能在实际运行中全都生效。
    custom_skills = bool(getattr(version, "skills_custom", False)) if version is not None else False
    bound_skill_ids = _as_list(version.skills if version is not None else None)

    public_skill_metas: List[Dict[str, Any]] = []
    try:
        from app.services.ai.skill_resolver import list_global_skill_metas

        public_skill_metas = list(list_global_skill_metas() or [])
    except Exception:  # noqa: BLE001 —— 取不到就退回"只列已绑定的"，不能让整个弹框失败
        logger.debug("[agent-scope] failed to list global skills", exc_info=True)
    public_skill_labels = {
        str(meta.get("id")): str(meta.get("name") or meta.get("id"))
        for meta in public_skill_metas
        if str(meta.get("id") or "").strip()
    }

    if custom_skills:
        # 白名单：只列它真正会加载的那些
        candidate_skill_ids = [sid for sid in bound_skill_ids if sid]
    else:
        # 全量公共技能：启用中的都算（enabled=false 的技能不加载，列出来只会误导）
        candidate_skill_ids = [
            str(meta.get("id"))
            for meta in public_skill_metas
            if str(meta.get("id") or "").strip()
            and str(meta.get("enabled", "true")).lower() != "false"
        ]
        if not candidate_skill_ids:
            # 目录不可用时的兜底：至少把已绑定的列出来
            candidate_skill_ids = list(bound_skill_ids)

    # 自定义 API 工具：名字 → 注册表里填的业务分组。
    # 前端要按「业务分组优先、否则按关键字猜能力域」展示——与智能体编辑页同一套规则，
    # 所以必须把 group_name 带出去，否则弹框只能退回关键字，两个页面分组会对不上。
    api_tool_rows = (await db.execute(select(SysApiTool.name, SysApiTool.group_name))).all()
    api_group_names: Dict[str, str] = {}
    for name, group_name in api_tool_rows:
        clean_name = str(name or "").strip()
        if clean_name:
            api_group_names[clean_name] = str(group_name or "").strip()
    api_names = set(api_group_names)

    def tool_item(tool_id: str) -> Dict[str, Any]:
        item: Dict[str, Any] = {
            "id": tool_id,
            "label": tool_id,
            "forbidden_globally": tool_id in globally_forbidden_tools,
        }
        group_name = api_group_names.get(tool_id)
        if group_name:
            item["group_name"] = group_name
        return item

    groups: List[Dict[str, Any]] = []

    builtin = [t for t in plain_tools if t not in api_names]
    api_tools = [t for t in plain_tools if t in api_names]
    if builtin:
        groups.append({"key": "builtin_tools", "label": "内置工具", "items": [tool_item(t) for t in builtin]})
    if api_tools:
        groups.append({"key": "api_tools", "label": "自定义 API 工具", "items": [tool_item(t) for t in api_tools]})

    if mcp_pairs:
        # 分组标题用 MCP 名称，取不到就退回 server_id（不能因此不展示，否则用户配不了）
        server_ids = list(dict.fromkeys(server_id for server_id, _ in mcp_pairs))
        server_labels: Dict[str, str] = {}
        cache_rows = (
            await db.execute(
                select(McpToolCache.server_id, McpToolCache.tool_name)
            )
        ).all()
        server_tool_index = {(sid, tname) for sid, tname in cache_rows}
        for server_id in server_ids:
            server_labels[server_id] = server_id
        try:
            from app.models.mcp import McpServer

            for server in (
                await db.execute(select(McpServer).where(McpServer.id.in_(server_ids)))
            ).scalars().all():
                if getattr(server, "server_name", None):
                    server_labels[server.id] = server.server_name
        except Exception:  # noqa: BLE001 —— 仅影响分组标题，取不到就用 id
            logger.debug("[agent-scope] failed to resolve MCP server labels", exc_info=True)

        for server_id in server_ids:
            items = []
            for sid, tool_name in mcp_pairs:
                if sid != server_id:
                    continue
                # McpToolCache 里没有的工具说明缓存未同步，仍然展示（用户可见集合以绑定为准）
                if (sid, tool_name) not in server_tool_index:
                    logger.debug(
                        "[agent-scope] bound MCP tool %s/%s not in cache; showing anyway",
                        sid,
                        tool_name,
                    )
                items.append(tool_item(tool_name))
            if items:
                groups.append(
                    {
                        "key": f"mcp:{server_id}",
                        "label": server_labels.get(server_id) or server_id,
                        "items": items,
                    }
                )

    if candidate_skill_ids:
        public_items = [
            {
                "id": skill_id,
                "label": public_skill_labels.get(skill_id) or skill_id,
                "forbidden_globally": skill_id in globally_forbidden_skills,
            }
            for skill_id in candidate_skill_ids
        ]
        groups.append({"key": "public_skills", "label": "公共技能", "items": public_items})

    personal_items = []
    for meta in personal_skills or []:
        skill_id = str(meta.get("id") or "").strip()
        if not skill_id:
            continue
        personal_items.append(
            {
                "id": skill_id,
                "label": str(meta.get("name") or skill_id),
                "forbidden_globally": skill_id in globally_forbidden_skills,
            }
        )
    if personal_items:
        groups.append({"key": "personal_skills", "label": "个人技能", "items": personal_items})

    return {"agent_id": agent_id, "groups": groups}


def list_personal_skill_metas(user_info: Optional[Dict[str, Any]]) -> List[Dict[str, str]]:
    """当前用户的个人技能清单（扫描失败返回空列表，不影响弹框其它分区）。"""
    if not user_info:
        return []
    try:
        from app.services.ai.skill_resolver import (
            _scan_skill_dir,
            get_user_personal_skills_dir,
        )

        skills_dir = get_user_personal_skills_dir(user_info)
        if not skills_dir or not os.path.isdir(skills_dir):
            return []
        return _scan_skill_dir(skills_dir, "personal") or []
    except Exception:  # noqa: BLE001
        logger.debug("[agent-scope] failed to scan personal skills", exc_info=True)
        return []
