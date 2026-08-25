from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.metadata_service import MetadataService


@pytest.mark.asyncio
@pytest.mark.no_infrastructure
async def test_create_metric_updates_existing_metric_without_name_error(monkeypatch):
    existing_metric = SimpleNamespace(
        display_name="旧指标",
        description="旧描述",
        calculation_logic="count()",
        unit="个",
        tags=[],
        updated_at=None,
    )
    db = SimpleNamespace(
        execute=AsyncMock(
            return_value=SimpleNamespace(
                scalar_one_or_none=lambda: existing_metric,
            )
        ),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )

    monkeypatch.setattr(
        MetadataService,
        "_mark_dataset_as_modified",
        AsyncMock(),
    )

    result = await MetadataService.create_metric(
        db,
        dataset_id=1,
        data={
            "name": "existing_metric",
            "display_name": "新指标",
            "description": "新描述",
            "calculation_logic": "sum(amount)",
            "unit": "元",
            "tags": ["核心"],
        },
    )

    assert result is existing_metric
    assert existing_metric.display_name == "新指标"
    assert existing_metric.description == "新描述"
    assert existing_metric.calculation_logic == "sum(amount)"
    assert existing_metric.unit == "元"
    assert existing_metric.tags == ["核心"]
    assert isinstance(existing_metric.updated_at, datetime)
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(existing_metric)
