"""禁用公共技能：策略集合读取、同步读缓存与显式挂载过滤。

与 ``forbidden_tools`` 同源：都从 ``ResourcePermission`` 读、都跳过 admin、失败降级不抛。
差异只在于拦截点更多——注入（清单/扫描/点名）、工具读写、会话工作区物化、显式挂载，
以及**原生文件工具（Read/Glob/Grep）与 /api/v1/chat/fs 的读判定**。

读判定（``app/utils/fs_access.py``）是同步函数，而禁用集合要查库（异步），所以这里额外维护
一个进程内、带短 TTL 的**同步读缓存**：异步版本查到后写入，同步版本只读缓存，
**未命中按放行处理**（与加这道闸之前的行为完全一致），避免把 fs 判定变成会抛异常的路径。

**来源口径（scope）**：禁用只针对"平台发布的那一份"公共技能，个人技能与公共技能可能同名
（见 ``app/utils/skill_metadata.is_personal_skill_attachment``），因此凡是"取禁用集合/判禁用"
的入口都接受一个可选 ``scope``：传 ``personal`` 时走个人口径（集合恒为空，且不查库），
缓存键也按"个人 / 公共（含未指定）"分成两维，避免同名技能共用同一份判定结果。
"""

from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict
from typing import Any, Iterable, Optional, Tuple

from app.utils.skill_metadata import (
    is_personal_skill_attachment,
    is_personal_skill_scope,
)

logger = logging.getLogger(__name__)

FORBIDDEN_SKILL_RESOURCE_TYPE = "forbidden_skill"

# 同步读缓存的绝对有效期（秒）。它只是"最后一次异步查询结果"的副本，而每个真正的
# 判定边界（会话开始、/api/v1/chat/fs 请求、原生文件工具调用）都会先异步刷新一遍
# （见 ``prime_forbidden_skill_cache``），实际陈旧窗口远小于这个数。
FORBIDDEN_SKILL_CACHE_TTL_SECONDS = 60.0
# 异步预热节流：同一用户最多每 10s 查一次库。一轮会话里文件工具可能被调用上百次，
# 不节流等于把一次权限查询放大成每个工具调用一次。
FORBIDDEN_SKILL_CACHE_REFRESH_SECONDS = 10.0
_FORBIDDEN_SKILL_CACHE_MAX_ENTRIES = 512

# key = 规范化后的 user_id 字符串；value = (写入时刻 monotonic, 禁用技能 id 集合)
_forbidden_skill_cache: "OrderedDict[str, Tuple[float, frozenset[str]]]" = OrderedDict()
_forbidden_skill_cache_lock = threading.RLock()


def _normalize_skill_ids(skill_ids: Optional[Iterable[Any]]) -> frozenset[str]:
    return frozenset(
        str(skill_id).strip() for skill_id in (skill_ids or ()) if str(skill_id).strip()
    )


def _cache_key(user_id: Any) -> Optional[str]:
    if user_id is None:
        return None
    key = str(user_id).strip()
    return key or None


def resolve_user_id_from_user_info(user_info: Optional[dict]) -> Optional[str]:
    """从 ``user_info`` 取用户标识，顺序与 ``get_forbidden_skill_ids`` 的回退链一致。

    生产侧塞进请求上下文的是**原始** user_info（键为 u_id_val/id/user_id/uid），
    只找其中一个会让同步读缓存命中不到异步写入的那条。
    """
    info = user_info or {}
    if not isinstance(info, dict):
        return None
    for key in ("u_id_val", "id", "user_id", "uid"):
        raw = info.get(key)
        if raw is not None and str(raw).strip():
            return str(raw).strip()
    return None


def _resolve_current_user_id() -> Optional[str]:
    """身份兜底：agent ctx 优先，其次请求侧 contextvar（与异步版本同一口径）。"""
    try:
        from app.core.context import get_current_agent_context

        ctx = get_current_agent_context()
        if ctx is not None and getattr(ctx, "user_id", None) is not None:
            key = _cache_key(ctx.user_id)
            if key:
                return key
    except Exception:
        pass
    try:
        from app.utils.context import current_user_info

        return resolve_user_id_from_user_info(current_user_info.get() or {})
    except Exception:
        return None


def resolve_agent_scope(explicit_agent_id: Any = None) -> Optional[str]:
    """解析"当前智能体"作用域：显式参数 → agent ctx → 请求侧 contextvar。

    智能体级禁用是「用户 × 智能体」两维的，判定与缓存都必须带上这一维：只带用户会让
    "在 A 智能体里禁的技能"串到 B 智能体（或反之漏禁）。取不到就返回 ``None``，
    表示按全局口径处理（与未启用该功能时的行为一致）。
    """
    if explicit_agent_id is not None and str(explicit_agent_id).strip():
        return str(explicit_agent_id).strip()
    try:
        from app.core.context import get_current_agent_context

        ctx = get_current_agent_context()
        if ctx is not None and getattr(ctx, "agent_id", None):
            return str(ctx.agent_id).strip() or None
    except Exception:
        pass
    try:
        from app.utils.context import current_user_info

        info = current_user_info.get() or {}
        if isinstance(info, dict) and info.get("agent_id"):
            return str(info["agent_id"]).strip() or None
    except Exception:
        pass
    return None


def _scoped_cache_key(
    user_id: Any, agent_id: Any = None, scope: Any = None
) -> Optional[str]:
    """同步读缓存的键 = 身份 | 智能体作用域 [| 来源口径]。

    作用域段用 ``-`` 表示全局（无智能体上下文），与权限缓存 v6 的键格式同一约定。

    ``scope`` 只区分**个人口径**这一维（``...|personal``）：个人技能永不属于公共禁用集合，
    个人判定恒为空集，若与公共口径共用同一个键，向个人键写入空集就会把公共技能的禁用
    结果覆盖掉（反向亦然），表现为"同名公共/个人技能互相串状态"。公共与"未指定"共用
    同一维是刻意的：既有预热调用点（``prime_forbidden_skill_cache``）都不传 scope，若把
    ``global`` 单列一维，预热写的是未指定键、判定读的是 global 键，会永远未命中 →
    fail-open 漏禁公共技能。
    """
    base = _cache_key(user_id)
    if base is None:
        return None
    key = f"{base}|{resolve_agent_scope(agent_id) or '-'}"
    return f"{key}|personal" if is_personal_skill_scope(scope) else key


def remember_forbidden_skill_ids(
    user_id: Any,
    skill_ids: Optional[Iterable[Any]] = None,
    agent_id: Any = None,
    scope: Any = None,
) -> None:
    """把禁用集合写进同步读缓存（覆盖同 key 的旧值，超出容量按插入序淘汰）。

    键含智能体作用域与来源口径：同一用户在不同智能体里的禁用集合不同，共用键会互相覆盖，
    表现为"切个智能体就漏禁/误禁"；个人口径下**强制写入空集**——绝不接受调用方传入的 id
    集合，否则把公共技能的禁用状态顺手写进个人维，同步读判定就会拿它去拦个人技能。
    """
    key = _scoped_cache_key(user_id, agent_id, scope)
    if key is None:
        return
    if is_personal_skill_scope(scope):
        if _normalize_skill_ids(skill_ids):
            logger.debug(
                "[forbidden] 个人口径不接受禁用集合（个人技能永不被禁），已按空集写入：%s", key
            )
        normalized_ids: frozenset[str] = frozenset()
    else:
        normalized_ids = _normalize_skill_ids(skill_ids)
    entry = (time.monotonic(), normalized_ids)
    with _forbidden_skill_cache_lock:
        _forbidden_skill_cache.pop(key, None)
        _forbidden_skill_cache[key] = entry
        while len(_forbidden_skill_cache) > _FORBIDDEN_SKILL_CACHE_MAX_ENTRIES:
            _forbidden_skill_cache.popitem(last=False)


def clear_forbidden_skill_cache() -> None:
    """清空同步读缓存（测试用；权限变更后也可以显式调用）。"""
    with _forbidden_skill_cache_lock:
        _forbidden_skill_cache.clear()


def _read_cached_entry(key: Optional[str]) -> Optional[Tuple[float, frozenset[str]]]:
    if key is None:
        return None
    now = time.monotonic()
    with _forbidden_skill_cache_lock:
        entry = _forbidden_skill_cache.get(key)
        if entry is None:
            return None
        stored_at, skill_ids = entry
        if now - stored_at > FORBIDDEN_SKILL_CACHE_TTL_SECONDS:
            _forbidden_skill_cache.pop(key, None)
            return None
        _forbidden_skill_cache.move_to_end(key)
        return entry


def get_cached_forbidden_skill_ids(
    user_id: Any, agent_id: Any = None, scope: Any = None
) -> Optional[frozenset[str]]:
    """同步读缓存：命中返回集合，未命中 / 已过期返回 ``None``。

    键含智能体作用域与来源口径（见 ``_scoped_cache_key``）。
    """
    key = _scoped_cache_key(user_id, agent_id, scope)
    entry = _read_cached_entry(key)
    if entry is None:
        # 未命中即放行，这条日志是排查"为什么没拦住"的唯一线索。
        # 用 DEBUG 而非 WARNING：文件工具每次读都会走到这里，未预热是正常状态，
        # 打成 WARNING 会把日志刷满（查询失败那条仍是 logger.exception 的 ERROR 级）。
        logger.debug(
            "[forbidden] fs read-cache miss for user %s; read guard fails open", key
        )
        return None
    return entry[1]


def is_platform_skill_id_forbidden(
    skill_id: str,
    user_info: Optional[dict] = None,
    agent_id: Any = None,
    scope: Any = None,
) -> bool:
    """同步判定：某个**公共**技能 id 是否在当前用户的禁用集合里。

    ``scope`` 传 ``personal`` 时恒为 ``False``（个人技能不属于公共禁用集合，同名公共技能的
    禁用状态不连坐）：连缓存都不查，免得读到公共那一维的结果。

    **fail-open**：拿不到集合（未预热 / 已过期 / 查询失败）一律按"未禁用"处理。这个函数处在
    原生文件工具与文件浏览器接口的热路径上，把"权限服务抖动或尚未预热"解释成"所有技能目录
    都读不到"，会把合法功能（技能脚本、未禁技能的 SKILL.md）一起打死——禁用是收口措施，
    不该成为新的可用性单点。
    """
    if is_personal_skill_scope(scope):
        logger.debug(
            "[forbidden] 个人技能口径不适用公共禁用集合，直接放行 skill_id=%s", skill_id
        )
        return False
    clean_id = str(skill_id or "").strip()
    if not clean_id:
        return False
    user_id = resolve_user_id_from_user_info(user_info) or _resolve_current_user_id()
    skill_ids = get_cached_forbidden_skill_ids(user_id, agent_id, scope)
    if skill_ids is None:
        return False
    return clean_id in skill_ids


async def prime_forbidden_skill_cache(
    explicit_user_id: Any = None,
    *,
    user_info: Optional[dict] = None,
    max_age_seconds: Optional[float] = None,
    agent_id: Any = None,
    scope: Any = None,
) -> None:
    """异步预热同步读缓存（带节流，绝不抛异常）。

    调用点即"判定边界"：会话开始、``/api/v1/chat/fs`` 请求、原生文件工具调用。
    ``max_age_seconds`` 内的缓存直接复用，避免把权限查询放大成每个工具调用一次。

    ``agent_id`` 缺省时按 ``resolve_agent_scope`` 自动解析（会话内即为该会话的智能体）：
    读缓存键含作用域，预热点必须与同步读判定算出同一个键，否则预热写了全局键、
    判定去读智能体键，永远未命中——表现为"智能体级禁用对技能正文完全不起作用"。

    ``scope`` 是来源口径（缺省 = 公共口径），同样必须与同步读判定一致：键不一致就会永远
    未命中（个人口径只会是空集，不会漏禁公共技能）。
    """
    max_age = (
        FORBIDDEN_SKILL_CACHE_REFRESH_SECONDS
        if max_age_seconds is None
        else max_age_seconds
    )
    resolved_agent = resolve_agent_scope(agent_id)
    user_id = (
        _cache_key(explicit_user_id)
        or resolve_user_id_from_user_info(user_info)
        or _resolve_current_user_id()
    )
    cache_key = _scoped_cache_key(user_id, resolved_agent, scope)
    entry = _read_cached_entry(cache_key)
    if entry is not None and max_age > 0 and (time.monotonic() - entry[0]) <= max_age:
        return
    try:
        await get_forbidden_skill_ids(user_id, resolved_agent, scope=scope)
    except Exception:
        # get_forbidden_skill_ids 自身已吞掉查询异常；这里只兜住身份解析都失败的情况
        logger.debug(
            "[forbidden] Cache priming failed; fs read guard stays fail-open", exc_info=True
        )


async def get_forbidden_skill_ids(
    explicit_user_id: Any = None, explicit_agent_id: Any = None, *, scope: Any = None
) -> set[str]:
    """当前用户被禁的公共技能 id 集合（含角色级合并）。

    - 管理员不受限（与工具禁用一致：``roles`` 含 admin 或 ctx.is_admin 直接放行）
    - 无用户身份时返回空集合，但**留 warning 日志**（否则无法区分"没禁"与"没身份所以没查"）
    - 查询失败返回空集合 + error 日志。这里刻意**不**跟随工具/命令侧的 fail-closed：
      工具拒绝的是"这一次调用"，代价有限；技能侧一旦 fail-closed，权限服务抖动会让该用户
      **整个技能清单**不可用，代价与收益不对称。方向不同是刻意的取舍，用 error 级别保证可告警。
    - ``scope="personal"`` 走个人口径：禁用集合是"平台发布的那一份"的清单，个人技能永远不在
      其中，因此**直接返回空集且不查库**——个人技能不能用公共技能 id 去查禁用集合/白名单，
      同名时会把公共技能的禁用状态串到个人技能上。空集同时写进个人维缓存，让同步读判定
      与这里同口径（个人维恒为空，公共维不受影响）。
    """
    from app.core.context import get_current_agent_context

    ctx = get_current_agent_context()
    user_id = explicit_user_id or (ctx.user_id if ctx else None)
    # 作用域：显式参数优先，否则取会话上下文（两维都从同一处解析，避免各调用方各算一套）
    agent_id = resolve_agent_scope(explicit_agent_id)
    if not user_id:
        from app.utils.context import current_user_info

        info = current_user_info.get() or {}
        # 生产侧塞进 contextvar 的是**原始** user_info（键为 user_id/user_name/role），
        # 只找 u_id_val/id 会让这个回退成为死代码——见 workspace._resolve_identity_user_id。
        user_id = info.get("u_id_val") or info.get("id") or info.get("user_id") or info.get("uid")
    if not user_id:
        logger.warning("[forbidden] No user identity when resolving forbidden skills; allowing all")
        return set()
    if is_personal_skill_scope(scope):
        remember_forbidden_skill_ids(user_id, set(), agent_id, scope)
        logger.debug(
            "[forbidden] 个人技能口径：禁用集合只针对公共技能，跳过权限查询（user=%s）", user_id
        )
        return set()
    if explicit_user_id is None and ctx is not None and getattr(ctx, "is_admin", False):
        remember_forbidden_skill_ids(user_id, set(), agent_id, scope)
        return set()

    try:
        from app.core.orm import AsyncSessionLocal
        from app.services.permission_service import PermissionService

        async with AsyncSessionLocal() as session:
            perms = await PermissionService(session).get_user_permissions(
                int(user_id), agent_id
            )
        if "admin" in (perms.roles or set()):
            remember_forbidden_skill_ids(user_id, set(), agent_id, scope)
            return set()
        forbidden = {
            str(skill_id).strip()
            for skill_id in (perms.permissions.forbidden_skills or [])
            if str(skill_id).strip()
        }
        # 同步读判定（fs_access）只能读这份缓存，因此每次成功查询都要刷新它；
        # 失败**不写缓存**，让下一次调用真实重试，而不是把"空集合"锁在 TTL 里。
        remember_forbidden_skill_ids(user_id, forbidden, agent_id, scope)
        return forbidden
    except Exception:
        logger.exception(
            "[forbidden] Failed to resolve forbidden skills for user %s; failing open", user_id
        )
        return set()


def drop_forbidden_skill_items(
    items: Optional[Iterable[dict]],
    forbidden_ids: Optional[Iterable[str]],
) -> list[dict]:
    """显式挂载过滤：丢掉被禁的技能附件，其他类型附件原样保留。

    用户的挂载动作是"绕过快捷入口直接指定"，因此这里必须拦——否则禁用形同虚设。

    只禁**公共**技能：个人技能与公共技能可能同名，若这里不看 scope，用户自建的
    同名个人技能会在显式挂载时被静默丢弃。与 `sanitize_forbidden_skill_context`
    的 `blocked_ids = forbidden - personal_ids` 必须同口径，故复用同一判定函数
    （``is_personal_skill_attachment``：附件顶层 ``scope`` 与 ``skillMeta/skill_meta.scope``
    两处都看）。挂载列表可能是混合来源（个人 + 公共），因此来源判定必须**逐项**做。
    """
    kept = list(items or [])
    forbidden = {str(skill_id).strip() for skill_id in (forbidden_ids or []) if str(skill_id).strip()}
    if not forbidden:
        return kept

    retained: list[dict] = []
    dropped: list[str] = []
    for item in kept:
        if (
            isinstance(item, dict)
            and item.get("type") == "skill"
            and str(item.get("url") or "").strip() in forbidden
            and not is_personal_skill_attachment(item)
        ):
            dropped.append(str(item.get("url") or "").strip())
            continue
        retained.append(item)
    if dropped:
        # 技能被丢弃此前完全静默：用户看到「已挂载」却拿不到，线上也查不到任何线索
        logger.warning(
            "[forbidden] Dropped explicitly mounted forbidden skill(s): %s", ", ".join(dropped)
        )
    return retained
