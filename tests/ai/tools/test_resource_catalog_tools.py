"""Tests for list_accessible_datasets / list_accessible_knowledge_bases system tools."""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ai.tools.registry import ToolRegistry

pytestmark = pytest.mark.no_infrastructure


def test_resource_catalog_tools_are_system_implicit():
    tool_names = {getattr(tool, "name", "") for tool in ToolRegistry.get_system_implicit_tools()}
    assert "list_accessible_datasets" in tool_names
    assert "list_accessible_knowledge_bases" in tool_names
    assert ToolRegistry._registry["list_accessible_datasets"].name == "list_accessible_datasets"
    description = str(getattr(ToolRegistry._registry["list_accessible_datasets"], "description", "") or "")
    assert "已启用" in description
    assert "未启用" in description
    assert (
        ToolRegistry._registry["list_accessible_knowledge_bases"].name
        == "list_accessible_knowledge_bases"
    )


@pytest.mark.asyncio
async def test_list_accessible_datasets_requires_user_context():
    from app.services.ai.tools.resource_catalog_tools import list_accessible_datasets

    with patch(
        "app.services.ai.tools.resource_catalog_tools.get_current_agent_context",
        return_value=None,
    ):
        result = await list_accessible_datasets.ainvoke({})

    assert "无法识别当前用户" in result or "User context" in result


@pytest.mark.asyncio
async def test_list_accessible_datasets_returns_lightweight_fields():
    from app.services.ai.tools.resource_catalog_tools import list_accessible_datasets

    ctx = MagicMock()
    ctx.user_id = 7
    ctx.is_admin = False

    row = SimpleNamespace(
        id=11,
        name="orders",
        display_name="客户订单",
        description="订单主数据备注",
        status=1,
    )

    db = AsyncMock()
    db_cm = MagicMock()
    db_cm.__aenter__ = AsyncMock(return_value=db)
    db_cm.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.services.ai.tools.resource_catalog_tools.get_current_agent_context",
        return_value=ctx,
    ), patch(
        "app.services.ai.tools.resource_catalog_tools.AsyncSessionLocal",
        return_value=db_cm,
    ), patch(
        "app.services.ai.tools.resource_catalog_tools.MetadataService.list_accessible_dataset_options",
        AsyncMock(return_value=[row]),
    ) as mock_list:
        result = await list_accessible_datasets.ainvoke({})

    payload = json.loads(result)
    assert payload["count"] == 1
    assert payload["items"] == [
        {
            "id": 11,
            "name": "orders",
            "display_name": "客户订单",
            "description": "订单主数据备注",
            "status": 1,
        }
    ]
    mock_list.assert_awaited_once()
    kwargs = mock_list.await_args.kwargs
    assert kwargs["user_id"] == 7
    assert kwargs["is_admin"] is False
    assert kwargs["status"] == 1


@pytest.mark.asyncio
async def test_list_accessible_knowledge_bases_filters_by_access():
    from app.services.ai.tools.resource_catalog_tools import list_accessible_knowledge_bases

    ctx = MagicMock()
    ctx.user_id = 7
    ctx.is_admin = False
    ctx.user_dimensions = {"user_name": "alice"}

    kb_allowed = SimpleNamespace(
        ragflow_dataset_id="kb-1",
        name="运维手册",
        description="机房 SOP",
        notes="内部备注",
        visibility="team",
        owner="ops",
    )
    kb_denied = SimpleNamespace(
        ragflow_dataset_id="kb-2",
        name="机密库",
        description="x",
        notes="y",
        visibility="private",
        owner="sec",
    )

    db = AsyncMock()
    db_cm = MagicMock()
    db_cm.__aenter__ = AsyncMock(return_value=db)
    db_cm.__aexit__ = AsyncMock(return_value=None)

    execute_result = MagicMock()
    execute_result.scalars.return_value.all.return_value = [kb_allowed, kb_denied]
    db.execute = AsyncMock(return_value=execute_result)

    perm = MagicMock()
    perm.get_knowledge_base_access = AsyncMock(
        return_value={
            "is_admin": False,
            "accessible_ids": {"kb-1"},
            "writable_ids": set(),
        }
    )

    with patch(
        "app.services.ai.tools.resource_catalog_tools.get_current_agent_context",
        return_value=ctx,
    ), patch(
        "app.services.ai.tools.resource_catalog_tools.AsyncSessionLocal",
        return_value=db_cm,
    ), patch(
        "app.services.ai.tools.resource_catalog_tools.PermissionService",
        return_value=perm,
    ):
        result = await list_accessible_knowledge_bases.ainvoke({})

    payload = json.loads(result)
    assert payload["count"] == 1
    assert payload["items"] == [
        {
            "ragflow_dataset_id": "kb-1",
            "name": "运维手册",
            "description": "机房 SOP",
            "notes": "内部备注",
            "visibility": "team",
            "owner": "ops",
        }
    ]
    perm.get_knowledge_base_access.assert_awaited_once_with(7, "alice")
