"""禁用公共技能：策略集合读取与显式挂载过滤。

与 ``forbidden_tools`` 同源：都从 ``ResourcePermission`` 读、都跳过 admin、失败降级不抛。
差异只在于拦截点更多——注入（清单/扫描/点名）、工具读写、会话工作区物化、显式挂载。
"""

from __future__ import annotations

import logging
from typing import Any, Iterable, Optional

logger = logging.getLogger(__name__)

FORBIDDEN_SKILL_RESOURCE_TYPE = "forbidden_skill"


async def get_forbidden_skill_ids(explicit_user_id: Any = None) -> set[str]:
    """当前用户被禁的公共技能 id 集合（含角色级合并）。

    - 管理员不受限（与工具禁用一致：``roles`` 含 admin 或 ctx.is_admin 直接放行）
    - 无用户身份时返回空集合（未登录链路不额外收紧）
    - 查询失败只记日志并返回空集合：技能链路各处（``list_skill_metas`` 等）本来就是
      "出错即降级为空"的风格，这里保持一致，避免把权限服务的抖动放大成会话不可用
    """
    from app.core.context import get_current_agent_context

    ctx = get_current_agent_context()
    user_id = explicit_user_id or (ctx.user_id if ctx else None)
    if not user_id:
        from app.utils.context import current_user_info

        info = current_user_info.get() or {}
        user_id = info.get("u_id_val") or info.get("id")
    if not user_id:
        return set()
    if explicit_user_id is None and ctx is not None and getattr(ctx, "is_admin", False):
        return set()

    try:
        from app.core.orm import AsyncSessionLocal
        from app.services.permission_service import PermissionService

        async with AsyncSessionLocal() as session:
            perms = await PermissionService(session).get_user_permissions(int(user_id))
        if "admin" in (perms.roles or set()):
            return set()
        return {
            str(skill_id).strip()
            for skill_id in (perms.permissions.forbidden_skills or [])
            if str(skill_id).strip()
        }
    except Exception:
        logger.exception("Failed to resolve forbidden skills for user %s", user_id)
        return set()


def drop_forbidden_skill_items(
    items: Optional[Iterable[dict]],
    forbidden_ids: Optional[Iterable[str]],
) -> list[dict]:
    """显式挂载过滤：丢掉被禁的技能附件，其他类型附件原样保留。

    用户的挂载动作是"绕过快捷入口直接指定"，因此这里必须拦——否则禁用形同虚设。
    """
    kept = list(items or [])
    forbidden = {str(skill_id).strip() for skill_id in (forbidden_ids or []) if str(skill_id).strip()}
    if not forbidden:
        return kept
    return [
        item
        for item in kept
        if not (
            isinstance(item, dict)
            and item.get("type") == "skill"
            and str(item.get("url") or "").strip() in forbidden
        )
    ]
