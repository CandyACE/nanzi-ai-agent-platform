"""Runtime lookup rules for the AI model registry.

The registry's ``model_id`` is the stable runtime identity.  Display names
remain supported as a single-record legacy alias, but they must never win over
an exact ID or silently select an arbitrary record.
"""

from __future__ import annotations

from typing import Iterable, Any


class ModelRegistryError(RuntimeError):
    """Base error for a model registry resolution failure."""


class ModelDisabledError(ModelRegistryError):
    """Raised when a configured model exists but is disabled."""

    def __init__(self, model: str):
        super().__init__(f"模型已禁用，无法调用：{model}")
        self.model = model


class ModelNameAmbiguousError(ModelRegistryError):
    """Raised when a legacy display-name alias matches multiple records."""

    def __init__(self, model: str):
        super().__init__(f"模型名称不唯一，请改用 model_id：{model}")
        self.model = model


def _is_active(record: Any) -> bool:
    return bool(getattr(record, "is_active", False))


def resolve_model_record(*, exact_record: Any | None, named_records: Iterable[Any], model: str | None = None):
    """Resolve one registry row using exact ID first, then a unique name.

    ``exact_record`` deliberately includes inactive rows.  This is what lets
    callers distinguish “not registered” from “registered but disabled” and
    prevents a disabled model from falling through to system credentials.
    """

    if exact_record is not None:
        if not _is_active(exact_record):
            raise ModelDisabledError(model or str(getattr(exact_record, "model_id", "")))
        return exact_record

    records = list(named_records)
    if len(records) > 1:
        raise ModelNameAmbiguousError(model or str(getattr(records[0], "name", "")))
    if not records:
        return None
    record = records[0]
    if not _is_active(record):
        raise ModelDisabledError(model or str(getattr(record, "name", "")))
    return record


async def lookup_registered_model(model: str):
    """Look up a model by exact ``model_id`` or a unique legacy name alias."""

    from sqlalchemy import select

    from app.core.orm import AsyncSessionLocal
    from app.models.ai_model import AIModel

    normalized = str(model or "").strip()
    if not normalized:
        return None

    async with AsyncSessionLocal() as session:
        exact_result = await session.execute(
            select(AIModel).where(AIModel.model_id == normalized)
        )
        exact_record = exact_result.scalars().first()
        if exact_record is not None:
            return resolve_model_record(
                exact_record=exact_record,
                named_records=[],
                model=normalized,
            )

        named_result = await session.execute(
            select(AIModel).where(AIModel.name == normalized)
        )
        return resolve_model_record(
            exact_record=None,
            named_records=named_result.scalars().all(),
            model=normalized,
        )
