import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ai.context_compaction_log_service import ContextCompactionLogService


pytestmark = pytest.mark.no_infrastructure


def _pipeline_mock():
    pipe = AsyncMock()
    # redis-py pipeline commands enqueue synchronously; only execute is awaited.
    pipe.rpush = MagicMock()
    pipe.ltrim = MagicMock()
    pipe.expire = MagicMock()
    pipe.__aenter__ = AsyncMock(return_value=pipe)
    pipe.__aexit__ = AsyncMock(return_value=False)
    pipe.execute = AsyncMock(return_value=[1, True, True])
    return pipe


@pytest.mark.asyncio
async def test_append_uses_conversation_key_json_and_seven_day_retention():
    redis = AsyncMock()
    pipe = _pipeline_mock()
    redis.pipeline = MagicMock(return_value=pipe)
    service = ContextCompactionLogService()
    record = {
        "event_id": "event-1",
        "event_type": "context_summarized",
        "source": "platform",
        "stage": "pre_route",
        "conversation_id": "conversation-1",
        "occurred_at": "2026-08-22T10:00:00+00:00",
        "preview": "历史摘录",
    }

    with patch(
        "app.services.ai.context_compaction_log_service.get_redis",
        new_callable=AsyncMock,
        return_value=redis,
    ):
        assert await service.append("user-1", "conversation-1", record) is True

    key = "conversation:user-1:conversation-1:context_compactions_v1"
    payload = json.loads(pipe.rpush.call_args.args[1])
    assert pipe.rpush.call_args.args[0] == key
    assert payload == record
    pipe.ltrim.assert_called_once_with(key, -service.MAX_RECORDS, -1)
    pipe.expire.assert_called_once_with(key, service.TTL_SECONDS)
    pipe.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_records_preserves_order_and_skips_malformed_json():
    redis = AsyncMock()
    redis.lrange = AsyncMock(
        return_value=[
            json.dumps({"event_id": "first"}).encode(),
            b"not-json",
            json.dumps({"event_id": "second"}),
        ]
    )
    service = ContextCompactionLogService()

    with patch(
        "app.services.ai.context_compaction_log_service.get_redis",
        new_callable=AsyncMock,
        return_value=redis,
    ):
        records = await service.list_records("user-1", "conversation-1")

    assert [record["event_id"] for record in records] == ["first", "second"]
    redis.lrange.assert_awaited_once_with(
        "conversation:user-1:conversation-1:context_compactions_v1", 0, -1
    )


@pytest.mark.asyncio
async def test_redis_unavailable_is_best_effort():
    service = ContextCompactionLogService()

    with patch(
        "app.services.ai.context_compaction_log_service.get_redis",
        new_callable=AsyncMock,
        return_value=None,
    ):
        assert await service.append("user-1", "conversation-1", {}) is False
        assert await service.list_records("user-1", "conversation-1") == []


def test_build_event_record_keeps_structured_metrics_and_truncates_preview():
    service = ContextCompactionLogService()
    record = service.build_event_record(
        {
            "type": "context_compression",
            "details": "x" * 500,
            "summary_chars": 500,
            "status": "success",
        },
        user_id="user-1",
        conversation_id="conversation-1",
        trace_id="trace-1",
        source="agentscope",
        stage="agent_runtime",
        agent_name="主助手",
    )

    assert record["event_type"] == "context_compression"
    assert record["source"] == "agentscope"
    assert record["stage"] == "agent_runtime"
    assert record["trace_id"] == "trace-1"
    assert record["summary_chars"] == 500
    assert len(record["preview"]) == service.PREVIEW_LIMIT
