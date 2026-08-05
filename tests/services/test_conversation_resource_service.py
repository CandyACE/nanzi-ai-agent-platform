from unittest.mock import AsyncMock, patch

import pytest

from app.services.conversation_resource_service import ConversationResourceService


pytestmark = pytest.mark.no_infrastructure


@pytest.mark.asyncio
async def test_replace_keeps_only_explicit_project_resources():
    redis = AsyncMock()
    with patch("app.services.conversation_resource_service.get_redis", new_callable=AsyncMock, return_value=redis):
        scope = await ConversationResourceService.replace(
            7,
            "conv-1",
            {
                "project_name": "销售分析",
                "datasets": [{"id": "sales_ds", "name": "销售数据"}, {"name": "无 ID"}],
                "knowledge_bases": [{"id": "kb-1"}],
                "skills": [{"id": "skill-1"}],
                "mcp_tools": [{"id": "mcp-1", "name": "mcp_demo"}],
            },
        )

    assert scope["project_name"] == "销售分析"
    assert [item["id"] for item in scope["datasets"]] == ["sales_ds"]
    assert [item["id"] for item in scope["mcp_tools"]] == ["mcp-1"]
    redis.set.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_many_uses_one_redis_mget_for_history_scopes():
    redis = AsyncMock()
    redis.mget.return_value = [
        '{"project_name":"p1","datasets":[]}',
        None,
    ]
    with patch("app.services.conversation_resource_service.get_redis", new_callable=AsyncMock, return_value=redis):
        scopes = await ConversationResourceService.get_many(7, ["conv-1", "conv-2"])

    redis.mget.assert_awaited_once_with([
        "conversation:7:conv-1:resource_scope_v1",
        "conversation:7:conv-2:resource_scope_v1",
    ])
    assert scopes["conv-1"]["project_name"] == "p1"
    assert scopes["conv-2"]["datasets"] == []
