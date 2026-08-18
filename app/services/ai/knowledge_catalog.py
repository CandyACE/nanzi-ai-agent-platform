"""统一的授权知识库目录与泛化相关性判定。"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Literal, Optional

from sqlalchemy import select

from app.core.orm import AsyncSessionLocal
from app.models.knowledge import KnowledgeBaseMetadata
from app.services.permission_service import PermissionService


logger = logging.getLogger(__name__)

CatalogStatus = Literal["available", "empty", "unavailable"]


@dataclass(frozen=True)
class KnowledgeBaseCatalogItem:
    """经过权限过滤、可用于路由的知识库目录元数据。"""

    ragflow_dataset_id: str
    name: str
    description: str = ""
    tags: Any = None
    notes: str = ""
    visibility: str = ""
    owner: str = ""


@dataclass(frozen=True)
class AuthorizedKnowledgeCatalog:
    """当前用户知识库目录快照；状态与空结果必须可区分。"""

    status: CatalogStatus
    items: tuple[KnowledgeBaseCatalogItem, ...] = ()
    error: Optional[str] = None

    @property
    def has_effective_scope(self) -> bool:
        return self.status == "available" and bool(self.items)


@dataclass(frozen=True)
class KnowledgeCatalogMatch:
    """目录相关性证据，不包含任何额外权限。"""

    status: CatalogStatus
    matched_ids: tuple[str, ...] = ()
    confidence: Literal["none", "weak", "strong"] = "none"


_CJK_RUN = re.compile(r"[\u4e00-\u9fff]+")
_ALNUM_TOKEN = re.compile(r"[a-zA-Z][a-zA-Z0-9_]{1,}")

# 只过滤动作词、疑问词和目录/文档类型的泛化词，不表达任何业务领域。
_GENERIC_FRAGMENTS = frozenset(
    {
        "帮我",
        "帮忙",
        "请问",
        "一下",
        "看看",
        "查看",
        "查询",
        "查一",
        "查下",
        "查找",
        "搜索",
        "了解",
        "如何",
        "怎么",
        "什么",
        "哪些",
        "是否",
        "能否",
        "有没有",
        "政策",
        "规定",
        "制度",
        "规范",
        "手册",
        "文档",
        "资料",
        "信息",
        "内容",
        "the",
        "and",
        "for",
        "with",
        "what",
        "how",
        "please",
    }
)


def _clean(value: Any) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ")
    return " ".join(text.split()).strip()


def _metadata_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple, set)):
        try:
            return _clean(json.dumps(value, ensure_ascii=False, sort_keys=True))
        except (TypeError, ValueError):
            return _clean(value)
    return _clean(value)


def _signals(text: Any) -> set[str]:
    """提取中英文可复用的字符/词片段，不依赖领域词表。"""
    raw = _clean(text).lower()
    signals: set[str] = set()
    for run in _CJK_RUN.findall(raw):
        if len(run) < 2:
            continue
        for index in range(len(run) - 1):
            fragment = run[index : index + 2]
            if fragment not in _GENERIC_FRAGMENTS:
                signals.add(fragment)
    for token in _ALNUM_TOKEN.findall(raw):
        if token not in _GENERIC_FRAGMENTS:
            signals.add(token)
    return signals


def _item_signals(item: KnowledgeBaseCatalogItem) -> tuple[set[str], set[str]]:
    name_signals = _signals(item.name)
    all_signals = set(name_signals)
    for value in (item.description, item.tags, item.notes):
        all_signals.update(_signals(_metadata_text(value)))
    return name_signals, all_signals


def match_knowledge_catalog(
    query: str,
    catalog: AuthorizedKnowledgeCatalog | None,
) -> KnowledgeCatalogMatch:
    """用目录元数据提供高/低置信证据；不命中不代表没有检索能力。"""
    if catalog is None:
        return KnowledgeCatalogMatch(status="unavailable")
    if catalog.status != "available":
        return KnowledgeCatalogMatch(status=catalog.status)

    query_signals = _signals(query)
    if not query_signals or not catalog.items:
        return KnowledgeCatalogMatch(status="available")

    scored: list[tuple[float, int, str]] = []
    for item in catalog.items:
        name_signals, all_signals = _item_signals(item)
        overlap = query_signals & all_signals
        name_overlap = query_signals & name_signals
        if not overlap:
            continue
        query_coverage = len(overlap) / len(query_signals)
        metadata_coverage = len(overlap) / max(len(all_signals), 1)
        score = 0.68 * query_coverage + 0.22 * metadata_coverage
        score += min(len(name_overlap), 3) * 0.1
        scored.append((score, len(overlap), item.ragflow_dataset_id))

    if not scored:
        return KnowledgeCatalogMatch(status="available")

    scored.sort(reverse=True)
    best_score, overlap_count, best_id = scored[0]
    # 至少两个有区分度的片段，或一个名称片段加一个高覆盖率，才升级为强证据。
    best_item = next(
        (item for item in catalog.items if item.ragflow_dataset_id == best_id),
        None,
    )
    name_overlap_count = len(query_signals & _item_signals(best_item)[0]) if best_item else 0
    strong = overlap_count >= 2 and (
        best_score >= 0.24 or name_overlap_count >= 2
    )
    if strong:
        return KnowledgeCatalogMatch(
            status="available",
            matched_ids=(best_id,),
            confidence="strong",
        )
    return KnowledgeCatalogMatch(
        status="available",
        matched_ids=(best_id,),
        confidence="weak",
    )


def _to_item(row: Any) -> KnowledgeBaseCatalogItem | None:
    dataset_id = _clean(getattr(row, "ragflow_dataset_id", None))
    name = _clean(getattr(row, "name", None))
    if not dataset_id or not name:
        return None
    return KnowledgeBaseCatalogItem(
        ragflow_dataset_id=dataset_id,
        name=name,
        description=_clean(getattr(row, "description", None)),
        tags=getattr(row, "tags", None),
        notes=_clean(getattr(row, "notes", None)),
        visibility=_clean(getattr(row, "visibility", None)),
        owner=_clean(getattr(row, "owner", None)),
    )


async def fetch_authorized_knowledge_catalog(
    db: Any,
    *,
    user_id: Optional[int],
    user_name: Optional[str] = None,
    is_admin: bool = False,
    permission_service: Any = None,
) -> AuthorizedKnowledgeCatalog:
    """在已有数据库会话中读取完整的、权限过滤后的知识库目录。"""
    if user_id is None:
        return AuthorizedKnowledgeCatalog(status="empty")

    access = await (permission_service or PermissionService(db)).get_knowledge_base_access(
        int(user_id),
        user_name,
    )
    rows = list(
        (
            await db.execute(
                select(KnowledgeBaseMetadata)
                .where(KnowledgeBaseMetadata.status != "deleted")
                .order_by(KnowledgeBaseMetadata.name.asc())
            )
        )
        .scalars()
        .all()
    )
    allowed_ids = access.get("accessible_ids")
    if allowed_ids is not None:
        allowed_ids = {str(value).strip() for value in allowed_ids if str(value).strip()}
        rows = [
            row
            for row in rows
            if _clean(getattr(row, "ragflow_dataset_id", None)) in allowed_ids
        ]

    items = tuple(item for row in rows if (item := _to_item(row)) is not None)
    return AuthorizedKnowledgeCatalog(
        status="available" if items else "empty",
        items=items,
    )


async def load_authorized_knowledge_catalog(
    *,
    user_id: Optional[int],
    user_name: Optional[str] = None,
    is_admin: bool = False,
) -> AuthorizedKnowledgeCatalog:
    """打开独立会话读取目录；异常状态不伪装成“无匹配”。"""
    if user_id is None:
        return AuthorizedKnowledgeCatalog(status="empty")
    try:
        async with AsyncSessionLocal() as db:
            return await fetch_authorized_knowledge_catalog(
                db,
                user_id=user_id,
                user_name=user_name,
                is_admin=is_admin,
            )
    except Exception as exc:  # noqa: BLE001 - routing must remain available
        logger.warning("Failed to load authorized knowledge catalog: %s", exc)
        return AuthorizedKnowledgeCatalog(status="unavailable", error=str(exc))


__all__ = [
    "AuthorizedKnowledgeCatalog",
    "CatalogStatus",
    "KnowledgeBaseCatalogItem",
    "KnowledgeCatalogMatch",
    "fetch_authorized_knowledge_catalog",
    "load_authorized_knowledge_catalog",
    "match_knowledge_catalog",
]
