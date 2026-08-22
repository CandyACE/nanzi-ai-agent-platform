"""资源范围收敛：把客户端提交的资源 token 收敛为用户可见目录中的可信快照。

会话（EmbedChat）与定时任务共用同一套语义：不在授权目录内的数据集 / 知识库 /
技能 / MCP 条目一律丢弃，范围只能收窄，不能借此扩大权限。
"""

from __future__ import annotations

import os
from typing import Any, Dict

from sqlalchemy.ext.asyncio import AsyncSession

def has_any_resource(scope: Dict[str, Any] | None) -> bool:
    """判断范围内是否挂载了任何资源（project_name 不算资源）。"""
    source = scope or {}
    return any(
        source.get(key)
        for key in ("datasets", "knowledge_bases", "skills", "mcp_tools")
    )


async def normalize_resource_scope_for_user(
    db: AsyncSession,
    user_info: Dict[str, Any],
    raw_scope: Dict[str, Any],
) -> Dict[str, Any]:
    """把客户端提交的资源 token 收敛为指定用户可见目录中的可信快照。"""
    from app.models.knowledge import KnowledgeBaseMetadata
    from app.services.metadata_service import MetadataService
    from app.core.config import settings
    from app.services.ai.skill_resolver import get_user_personal_skills_dir
    from app.services.permission_service import PermissionService
    from app.api.portal.endpoints.skills import parse_skill_metadata
    from sqlalchemy import and_, select
    from sqlalchemy.orm import joinedload

    raw_scope = raw_scope if isinstance(raw_scope, dict) else {}
    raw_user_id = user_info.get("user_id") or user_info.get("id")
    try:
        user_id = int(raw_user_id) if raw_user_id is not None else None
    except (TypeError, ValueError):
        user_id = None
    is_admin = user_info.get("role") == "admin"
    datasets = await MetadataService.list_accessible_dataset_options(
        db, user_id=user_id, is_admin=is_admin, status=1
    )
    dataset_by_token: Dict[str, Any] = {}
    for dataset in datasets:
        for token in (
            dataset.id,
            dataset.name,
            getattr(dataset, "dataset_name", None),
        ):
            if token is not None and str(token).strip():
                dataset_by_token[str(token).strip().casefold()] = dataset

    def normalize_dataset(item: Any) -> Dict[str, Any] | None:
        if not isinstance(item, dict):
            return None
        dataset = next(
            (
                dataset_by_token.get(str(item.get(key) or "").strip().casefold())
                for key in ("id", "dataset_name", "name")
                if str(item.get(key) or "").strip().casefold() in dataset_by_token
            ),
            None,
        )
        if dataset is None:
            return None
        return {
            "id": str(dataset.id),
            "name": str(getattr(dataset, "display_name", None) or dataset.name or dataset.id),
            "dataset_name": str(dataset.name or ""),
            "description": str(getattr(dataset, "description", None) or ""),
        }

    kb_access = await PermissionService(db).get_knowledge_base_access(
        int(user_id), user_info.get("user_name")
    ) if user_id is not None else {"is_admin": False, "accessible_ids": set()}
    kb_stmt = select(KnowledgeBaseMetadata).where(KnowledgeBaseMetadata.status != "deleted")
    kb_rows = list((await db.execute(kb_stmt)).scalars().all())
    allowed_kb_ids = kb_access.get("accessible_ids")
    kb_by_token: Dict[str, Any] = {}
    for kb in kb_rows:
        if allowed_kb_ids is not None and str(kb.ragflow_dataset_id) not in allowed_kb_ids:
            continue
        for token in (kb.ragflow_dataset_id, kb.name, kb.id):
            if token is not None and str(token).strip():
                kb_by_token[str(token).strip().casefold()] = kb

    def normalize_kb(item: Any) -> Dict[str, Any] | None:
        if not isinstance(item, dict):
            return None
        kb = next(
            (
                kb_by_token.get(str(item.get(key) or "").strip().casefold())
                for key in ("id", "dataset_id", "name")
                if str(item.get(key) or "").strip().casefold() in kb_by_token
            ),
            None,
        )
        if kb is None:
            return None
        return {
            "id": str(kb.ragflow_dataset_id),
            "name": str(kb.name or kb.ragflow_dataset_id),
            "description": str(kb.description or ""),
        }

    skill_by_token: Dict[tuple[str, str], Dict[str, Any]] = {}

    def collect_skills(root: str, scope_name: str) -> None:
        if not root or not os.path.isdir(root):
            return
        try:
            entries = os.listdir(root)
        except OSError:
            return
        for skill_id in entries:
            skill_dir = os.path.join(root, skill_id)
            skill_md = os.path.join(skill_dir, "SKILL.md")
            if not os.path.isdir(skill_dir) or skill_id.startswith(".") or not os.path.isfile(skill_md):
                continue
            meta = parse_skill_metadata(skill_id, skill_md)
            if str(meta.get("enabled", "true")).strip().lower() in {"false", "0", "no", "off"}:
                continue
            skill_by_token[(scope_name, skill_id.casefold())] = {
                "id": skill_id,
                "name": str(meta.get("name") or skill_id),
                "description": str(meta.get("description") or ""),
                "scope": scope_name,
            }

    collect_skills(str(getattr(settings, "SKILLS_DIR", "") or ""), "global")
    try:
        collect_skills(str(get_user_personal_skills_dir(user_info) or ""), "personal")
    except Exception:
        pass

    normalized_skills: list[Dict[str, Any]] = []
    for item in raw_scope.get("skills", []) or []:
        if not isinstance(item, dict):
            continue
        skill_id = str(item.get("id") or "").strip()
        requested_scope = str(item.get("scope") or "").strip().lower()
        candidates = (
            [(requested_scope, skill_id.casefold())]
            if requested_scope in {"global", "personal"}
            else [("global", skill_id.casefold()), ("personal", skill_id.casefold())]
        )
        skill = next((skill_by_token.get(key) for key in candidates if skill_by_token.get(key)), None)
        if skill:
            normalized_skills.append(skill)

    from app.models.mcp import McpServer, McpToolCache

    mcp_personal_cond = and_(
        McpServer.scope == "personal",
        McpServer.user_id == int(user_id) if user_id is not None else -1,
    )
    # 会话动态挂载仅允许个人已发布 MCP；平台 MCP 走智能体版本配置
    mcp_stmt = (
        select(McpToolCache)
        .join(McpToolCache.server)
        .options(joinedload(McpToolCache.server))
        .where(
            McpToolCache.is_published == True,  # noqa: E712
            McpToolCache.is_available == True,  # noqa: E712
            mcp_personal_cond if user_id is not None else False,
        )
    )
    mcp_rows = list((await db.execute(mcp_stmt)).scalars().unique().all())
    mcp_by_token: Dict[str, Dict[str, Any]] = {}
    for row in mcp_rows:
        server = row.server
        snapshot = {
            "id": str(row.id),
            "name": str(row.tool_name or ""),
            "description": str(row.tool_description or ""),
            "server_name": str(getattr(server, "server_name", None) or "Unknown"),
            "scope": str(getattr(server, "scope", None) or "global"),
        }
        if not snapshot["name"]:
            continue
        for token in (snapshot["id"], snapshot["name"]):
            if token.strip():
                mcp_by_token[token.strip().casefold()] = snapshot

    normalized_mcp_tools: list[Dict[str, Any]] = []
    seen_mcp_names: set[str] = set()
    for item in raw_scope.get("mcp_tools", []) or []:
        if not isinstance(item, dict):
            continue
        matched = None
        for key in ("id", "name"):
            token = str(item.get(key) or "").strip().casefold()
            if token and token in mcp_by_token:
                matched = mcp_by_token[token]
                break
        if not matched:
            continue
        name = matched["name"]
        if name in seen_mcp_names:
            continue
        seen_mcp_names.add(name)
        normalized_mcp_tools.append(matched)

    return {
        "project_name": str(raw_scope.get("project_name") or "").strip()[:100],
        "datasets": [item for raw in raw_scope.get("datasets", []) or [] if (item := normalize_dataset(raw))],
        "knowledge_bases": [item for raw in raw_scope.get("knowledge_bases", []) or [] if (item := normalize_kb(raw))],
        "skills": normalized_skills,
        "mcp_tools": normalized_mcp_tools,
    }
