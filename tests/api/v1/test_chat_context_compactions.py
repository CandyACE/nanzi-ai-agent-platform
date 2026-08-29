from unittest.mock import AsyncMock, patch

import pytest

from app.api.v1.endpoints import chat as chat_endpoint


pytestmark = pytest.mark.no_infrastructure


@pytest.mark.asyncio
async def test_context_compactions_returns_current_users_conversation_timeline():
    records = [
        {
            "event_id": "event-1",
            "conversation_id": "conversation-1",
            "event_type": "context_summarized",
            "source": "platform",
            "stage": "pre_route",
            "occurred_at": "2026-08-22T10:00:00+00:00",
            "preview": "历史摘录",
        }
    ]

    with patch(
        "app.api.v1.endpoints.chat.context_compaction_log_service.list_records",
        new_callable=AsyncMock,
        return_value=records,
    ) as list_records:
        response = await chat_endpoint.get_context_compactions(
            conversation_id="conversation-1",
            user_info={"user_id": 7},
        )

    list_records.assert_awaited_once_with("7", "conversation-1")
    assert response.data.count == 1
    assert response.data.records[0].model_dump(exclude_none=True) == records[0] | {
        "title": "上下文已压缩",
        "status": "success",
    }
    assert response.data.retention_seconds == 2592000


@pytest.mark.asyncio
async def test_context_compactions_never_accepts_a_user_id_from_the_request():
    with patch(
        "app.api.v1.endpoints.chat.context_compaction_log_service.list_records",
        new_callable=AsyncMock,
        return_value=[],
    ) as list_records:
        response = await chat_endpoint.get_context_compactions(
            conversation_id="conversation-1",
            user_info={"user_id": "owner-1", "id": "attacker-supplied"},
        )

    list_records.assert_awaited_once_with("owner-1", "conversation-1")
    assert response.data.records == []
    assert response.data.count == 0


@pytest.mark.asyncio
async def test_context_compactions_skips_invalid_record_without_failing_timeline():
    with patch(
        "app.api.v1.endpoints.chat.context_compaction_log_service.list_records",
        new_callable=AsyncMock,
        return_value=[
            {"event_id": "valid", "conversation_id": "c1", "event_type": "context_summarized",
             "source": "platform", "stage": "pre_route", "occurred_at": "now"},
            {"event_id": "broken", "event_type": "context_summarized"},
        ],
    ):
        response = await chat_endpoint.get_context_compactions(
            conversation_id="c1",
            user_info={"user_id": 7},
        )

    assert response.data.count == 1
    assert response.data.records[0].event_id == "valid"


@pytest.mark.asyncio
async def test_manual_context_compaction_uses_authenticated_user_and_returns_result():
    result = {
        "compacted": True,
        "dropped": 4,
        "kept": 6,
        "count": 1,
    }
    with patch(
        "app.api.v1.endpoints.chat.agent_service.manual_compact_conversation",
        new_callable=AsyncMock,
        return_value=result,
    ) as compact:
        response = await chat_endpoint.manual_context_compaction(
            conversation_id="conversation-1",
            user_info={"user_id": 7, "id": 999},
            request=chat_endpoint.ManualContextCompactionRequest(retain_ratio=0.5, mode="smart"),
        )

    compact.assert_awaited_once_with("7", "conversation-1", retain_ratio=0.5, mode="smart")
    assert response.data == result
