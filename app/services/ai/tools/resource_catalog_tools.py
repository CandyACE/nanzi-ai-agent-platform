"""System tools: list current user's accessible datasets and knowledge bases."""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from sqlalchemy import select

from app.core.context import get_current_agent_context
from app.core.orm import AsyncSessionLocal
from app.models.knowledge import KnowledgeBaseMetadata
from app.services.ai.tools.tool_compat import tool
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
            access = await PermissionService(db).get_knowledge_base_access(
                int(ctx.user_id),
                user_name,
            )
            stmt = select(KnowledgeBaseMetadata).where(
                KnowledgeBaseMetadata.status != "deleted"
            )
            rows = list((await db.execute(stmt)).scalars().all())
            allowed_ids = access.get("accessible_ids")
            items: list[dict[str, Any]] = []
            for row in rows:
                rag_id = str(getattr(row, "ragflow_dataset_id", None) or "").strip()
                if not rag_id:
                    continue
                if allowed_ids is not None and rag_id not in allowed_ids:
                    continue
                items.append(_knowledge_item(row))
            items.sort(key=lambda x: x.get("ragflow_dataset_id") or "")
            return json.dumps({"items": items, "count": len(items)}, ensure_ascii=False)
    except Exception as e:
        logger.error("[list_accessible_knowledge_bases] failed: %s", e, exc_info=True)
        return f"列出可访问知识库失败: {e}"
