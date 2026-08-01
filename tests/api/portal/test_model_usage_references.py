from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api.portal.endpoints.models import (
    _build_agent_model_reference,
    _delete_model_record,
    _should_include_agent_model_reference,
)


pytestmark = pytest.mark.no_infrastructure


def test_build_agent_model_reference_includes_navigation_and_status_metadata():
    version = SimpleNamespace(
        id="version-1",
        version_number=3,
        status="PUBLISHED",
    )
    agent = SimpleNamespace(
        id="agent-1",
        name="data-assistant",
        display_name="数据助手",
        is_enabled=True,
    )

    reference = _build_agent_model_reference(version, agent, ["主模型", "合成模型"])

    assert reference == {
        "kind": "agent_version",
        "key": "主模型,合成模型",
        "label": "智能体「数据助手」v3",
        "detail": "主模型、合成模型",
        "agent_id": "agent-1",
        "agent_name": "data-assistant",
        "version_id": "version-1",
        "version_number": 3,
        "version_status": "PUBLISHED",
        "agent_enabled": True,
    }


def test_archived_agent_versions_are_excluded_from_model_references():
    assert _should_include_agent_model_reference(SimpleNamespace(status="PUBLISHED")) is True
    assert _should_include_agent_model_reference(SimpleNamespace(status="DRAFT")) is True
    assert _should_include_agent_model_reference(SimpleNamespace(status="ARCHIVED")) is False


@pytest.mark.asyncio
async def test_delete_model_record_physically_removes_model():
    db = SimpleNamespace(delete=AsyncMock(), commit=AsyncMock())
    model = SimpleNamespace(id="model-1")

    await _delete_model_record(db, model)

    db.delete.assert_awaited_once_with(model)
    db.commit.assert_awaited_once_with()
