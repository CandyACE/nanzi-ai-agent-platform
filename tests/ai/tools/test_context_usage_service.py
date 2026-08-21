import pytest


pytestmark = pytest.mark.no_infrastructure


@pytest.mark.asyncio
async def test_context_usage_service_returns_budget_for_an_empty_conversation(monkeypatch):
    from app.services.ai.context_usage import estimate_context_usage

    async def fake_get_history(user_id, conversation_id, limit=None, offset=0):
        assert user_id == "user-1"
        assert conversation_id == "conversation-1"
        return []

    async def fake_config_get(key, default=None):
        return {
            "agent_context_max_tokens": "65536",
            "agent_context_overhead_headroom_tokens": "8192",
        }.get(key, default)

    monkeypatch.setattr(
        "app.services.ai.context_usage.memory_service.get_history",
        fake_get_history,
    )
    monkeypatch.setattr(
        "app.services.ai.context_usage.ConfigService.get",
        fake_config_get,
    )

    usage = await estimate_context_usage(
        user_id="user-1",
        conversation_id="conversation-1",
        runtime_model_info={
            "source": "runtime_override",
            "context_size": 65536,
            "completion_reserve_tokens": 16384,
            "prompt_overhead_reservation_tokens": 8192,
        },
        empty_history_is_zero=True,
    )

    assert usage["estimated_current_tokens"] == 0
    assert usage["context_messages"] == 0
    assert usage["physical_window"] == 65536
    assert usage["history_budget"] == 40960
    assert usage["request_input_budget"] == 49152
    assert usage["usage_percentage"] == 0.0
