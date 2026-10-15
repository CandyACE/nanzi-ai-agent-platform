from unittest.mock import AsyncMock, patch

import pytest

from app.services.conversation_resource_service import (
    TTL_SECONDS,
    ConversationResourceService,
    MountSyncUnavailable,
)


pytestmark = pytest.mark.no_infrastructure


@pytest.mark.asyncio
async def test_replace_writes_the_shared_thirty_day_ttl():
    """TTL 必须是共享常量，且真的传给了 Redis（此前重命名链路漏了 ex）。"""
    redis = AsyncMock()
    with patch("app.services.conversation_resource_service.get_redis", new_callable=AsyncMock, return_value=redis):
        await ConversationResourceService.replace(7, "conv-1", {"skills": [{"id": "s"}]})

    assert TTL_SECONDS == 2592000
    assert ConversationResourceService.TTL_SECONDS == TTL_SECONDS
    assert redis.set.await_args.kwargs["ex"] == TTL_SECONDS


@pytest.mark.asyncio
async def test_rewrite_skill_mounts_raises_when_redis_unavailable_in_strict_mode():
    """删除/下架链路需要知道「这一处没同步」，不能被混进「改了 0 个会话」。"""
    with patch(
        "app.services.conversation_resource_service.get_redis",
        new_callable=AsyncMock,
        side_effect=RuntimeError("redis down"),
    ):
        with pytest.raises(MountSyncUnavailable):
            await ConversationResourceService.rewrite_skill_mounts(
                skill_id="gone", strict_unavailable=True
            )
        # 重命名链路保持历史语义：静默降级为 0
        assert (
            await ConversationResourceService.rewrite_skill_mounts(
                skill_id="gone", new_skill_id="new"
            )
            == 0
        )


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
