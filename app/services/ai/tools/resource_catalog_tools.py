"""System tools: list current user's accessible datasets and knowledge bases."""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from app.core.context import get_current_agent_context
from app.core.orm import AsyncSessionLocal
from app.services.ai.tools.tool_compat import tool
from app.services.ai.knowledge_catalog import fetch_authorized_knowledge_catalog
from app.services.metadata_service import MetadataService
from app.services.permission_service import PermissionService

logger = logging.getLogger(__name__)


def _context_user_name(ctx: Any) -> Optional[str]:
    dims = getattr(ctx, "user_dimensions", None) or {}
    if not isinstance(dims, dict):
        return None
    raw = dims.get("user_name") or dims.get("username")
    if raw is None:
        return None
    name = str(raw).strip()
    return name or None


def _dataset_item(row: Any) -> dict[str, Any]:
    return {
        "id": getattr(row, "id", None),
        "name": getattr(row, "name", None) or "",
        "display_name": getattr(row, "display_name", None) or "",
        "description": getattr(row, "description", None) or "",
        "status": getattr(row, "status", None),
    }


def _knowledge_item(row: Any) -> dict[str, Any]:
    return {
        "ragflow_dataset_id": getattr(row, "ragflow_dataset_id", None) or "",
        "name": getattr(row, "name", None) or "",
        "description": getattr(row, "description", None) or "",
        "notes": getattr(row, "notes", None) or "",
        "visibility": getattr(row, "visibility", None) or "",
        "owner": getattr(row, "owner", None) or "",
    }


@tool
async def list_accessible_datasets() -> str:
    """列出当前用户有权限且已启用的 ChatBI 数据集轻量目录（id/名称/备注/状态等，不含表字段指标）。

    使用规则：
    - 当用户问「我有哪些数据集」「能查哪些数据」「数据集列表」时调用。
    - 仅返回 status=1（启用）的目录级信息；未启用的数据集不会出现。
    - 不要据此编造表结构或查询结果。
    """
    ctx = get_current_agent_context()
    if not ctx or not ctx.user_id:
        return "无法识别当前用户，拒绝列出数据集。"

    try:
        async with AsyncSessionLocal() as db:
            rows = await MetadataService.list_accessible_dataset_options(
                db,
                user_id=ctx.user_id,
                is_admin=bool(ctx.is_admin),
                status=1,
            )
            items = [_dataset_item(row) for row in rows]
            return json.dumps({"items": items, "count": len(items)}, ensure_ascii=False)
    except Exception as e:
        logger.error("[list_accessible_datasets] failed: %s", e, exc_info=True)
        return f"列出可访问数据集失败: {e}"


@tool
async def list_accessible_knowledge_bases() -> str:
    """列出当前用户有权限的知识库轻量目录（id/名称/备注等，不含文档正文）。

    使用规则：
    - 当用户问「我有哪些知识库」「能检索哪些文档库」「知识库列表」时调用。
    - 仅返回目录级信息；具体内容检索请使用 search_knowledge_base。
    """
    ctx = get_current_agent_context()
    if not ctx or not ctx.user_id:
        return "无法识别当前用户，拒绝列出知识库。"

    try:
        user_name = _context_user_name(ctx)
        async with AsyncSessionLocal() as db:
            catalog = await fetch_authorized_knowledge_catalog(
                db,
                user_id=int(ctx.user_id),
                user_name=user_name,
                is_admin=bool(ctx.is_admin),
                permission_service=PermissionService(db),
            )
            items = [_knowledge_item(row) for row in catalog.items]
            items.sort(key=lambda x: x.get("ragflow_dataset_id") or "")
            return json.dumps({"items": items, "count": len(items)}, ensure_ascii=False)
    except Exception as e:
        logger.error("[list_accessible_knowledge_bases] failed: %s", e, exc_info=True)
        return f"列出可访问知识库失败: {e}"


def _agent_item(agent: Any) -> dict[str, Any]:
    return {
        "agent_name": getattr(agent, "name", "") or "",
        "display_name": getattr(agent, "display_name", "") or getattr(agent, "name", "") or "",
        "description": getattr(agent, "description", "") or "",
        "capabilities": list(getattr(agent, "capabilities", None) or []),
    }


@tool
async def list_available_agents() -> str:
    """列出当前用户有权限访问且可运行的可用智能体/专家目录（包含 agent_name、展示名称、职责描述与核心能力）。

    使用规则：
    - 当用户问「我有哪些智能体」「能调用哪些专家」「可用智能体列表」时调用。
    - 在需要通过 sub_agent_call 委派子任务前，若需查询或确认可委派的智能体标识 (agent_name) 与核心能力，可调用此工具。
    - 仅返回已启用且当前用户有权限访问的可运行智能体；会自动排除当前会话自身智能体。
    """
    ctx = get_current_agent_context()
    if not ctx or not ctx.user_id:
        return "无法识别当前用户，拒绝列出可用智能体。"

    try:
        from app.services.ai.agent_manager import AgentManagerService
        from app.services.ai.tools.agent_delegate_tool import resolve_runnable_delegable_system_agents

        async with AsyncSessionLocal() as db:
            active_agents = await AgentManagerService.list_agents(db)
            delegable_agents = await resolve_runnable_delegable_system_agents(
                db,
                active_agents,
                user_id=ctx.user_id,
                is_admin=bool(ctx.is_admin),
                current_agent_id=getattr(ctx, "agent_id", None),
            )
            items = [_agent_item(a) for a in delegable_agents]
            return json.dumps({"items": items, "count": len(items)}, ensure_ascii=False)
    except Exception as e:
        logger.error("[list_available_agents] failed: %s", e, exc_info=True)
        return f"列出可用智能体失败: {e}"

