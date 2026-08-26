from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest


pytestmark = pytest.mark.no_infrastructure


class FakeCountingModel:
    async def count_tokens(self, *, messages, tools):
        roles = [getattr(message, "role", "") for message in messages or []]
        if not messages and tools:
            return 11
        if roles and all(role == "system" for role in roles):
            return 3
        if messages:
            return 7 if "system" not in roles else 21
        return 0


@pytest.mark.asyncio
async def test_estimate_context_breakdown_splits_system_tools_and_conversation_tokens():
    from app.services.ai.runtime.agentscope.context_breakdown import (
        estimate_context_breakdown,
    )

    messages = [
        SimpleNamespace(role="system"),
        SimpleNamespace(role="user"),
        SimpleNamespace(role="assistant"),
    ]
    tools = [{"type": "function", "function": {"name": "search"}}]

    result = await estimate_context_breakdown(FakeCountingModel(), messages, tools)

    assert result == {
        "system_prompt_tokens": 3,
        "tools_tokens": 11,
        "conversation_tokens": 7,
        "total_tokens": 21,
        "estimated": True,
        "source": "agentscope_count_tokens",
    }


@pytest.mark.asyncio
async def test_estimate_context_breakdown_does_not_raise_when_counting_fails():
    from app.services.ai.runtime.agentscope.context_breakdown import (
        estimate_context_breakdown,
    )

    class BrokenModel:
        async def count_tokens(self, *, messages, tools):
            raise RuntimeError("tokenizer unavailable")

    result = await estimate_context_breakdown(
        BrokenModel(),
        [SimpleNamespace(role="system")],
        [],
    )

    assert result["total_tokens"] == 0
    assert result["estimated"] is False
    assert result["source"] == "unavailable"


@pytest.mark.asyncio
async def test_model_call_stats_record_contains_context_breakdown():
    from app.services.ai.runtime.agentscope.middleware import ModelCallStatsMiddleware

    middleware = ModelCallStatsMiddleware(
        user_id="u1",
        conversation_id="c1",
        agent_name="main",
    )
    messages = [
        SimpleNamespace(role="system"),
        SimpleNamespace(role="user"),
        SimpleNamespace(role="assistant"),
    ]
    tools = [{"type": "function", "function": {"name": "search"}}]

    async def next_handler(**kwargs):
        del kwargs
        return SimpleNamespace(
            usage=SimpleNamespace(input_tokens=21, output_tokens=2),
            content=[],
        )

    scheduled = []
    with patch(
        "app.services.ai.runtime.agentscope.middleware._append_stat_to_redis",
        new=AsyncMock(),
    ) as append_stat, patch(
        "app.services.ai.runtime.agentscope.middleware.asyncio.ensure_future",
        side_effect=lambda coroutine: scheduled.append(coroutine),
    ):
        await middleware.on_model_call(
            agent=SimpleNamespace(),
            input_kwargs={
                "current_model": FakeCountingModel(),
                "messages": messages,
                "tools": tools,
            },
            next_handler=next_handler,
        )
        await scheduled[0]

    record = append_stat.await_args.args[1]
    assert record["context_breakdown"] == {
        "system_prompt_tokens": 3,
        "tools_tokens": 11,
        "conversation_tokens": 7,
        "total_tokens": 21,
        "estimated": True,
        "source": "agentscope_count_tokens",
    }


@pytest.mark.asyncio
async def test_model_call_reuses_full_input_token_count_for_completion_guard():
    from app.services.ai.runtime.agentscope.middleware import ModelCallStatsMiddleware

    class CountingGuardModel:
        model = "fake-model"
        context_size = 100

        def __init__(self):
            self.parameters = SimpleNamespace(max_tokens=10)
            self.count_calls = 0

        async def count_tokens(self, *, messages, tools):
            self.count_calls += 1
            roles = [getattr(message, "role", "") for message in messages or []]
            if not messages and tools:
                return 4
            if roles and all(role == "system" for role in roles):
                return 3
            return 20

    current_model = CountingGuardModel()
    middleware = ModelCallStatsMiddleware(
        user_id="u1",
        conversation_id="c1",
        agent_name="main",
    )

    async def next_handler(**kwargs):
        del kwargs
        return SimpleNamespace(
            usage=SimpleNamespace(input_tokens=20, output_tokens=2),
            content=[],
        )

    scheduled = []
    with patch(
        "app.services.ai.runtime.agentscope.middleware._append_stat_to_redis",
        new=AsyncMock(),
    ), patch(
        "app.services.ai.runtime.agentscope.middleware.asyncio.ensure_future",
        side_effect=lambda coroutine: scheduled.append(coroutine),
    ):
        await middleware.on_model_call(
            agent=SimpleNamespace(),
            input_kwargs={
                "current_model": current_model,
                "messages": [
                    SimpleNamespace(role="system"),
                    SimpleNamespace(role="user"),
                ],
                "tools": [{"type": "function", "function": {"name": "search"}}],
            },
            next_handler=next_handler,
        )
        await scheduled[0]

    assert current_model.count_calls == 3


def test_model_call_stats_api_schema_preserves_context_breakdown():
    from app.api.v1.endpoints.chat import ModelCallStatDetail

    detail = ModelCallStatDetail.model_validate(
        {
            "call_index": 1,
            "timestamp": "2026-08-22T00:00:00+00:00",
            "conversation_id": "c1",
            "agent_name": "main",
            "model_name": "demo",
            "input_message_count": 3,
            "has_tools_bound": True,
            "input_tokens": 21,
            "output_tokens": 2,
            "cache_input_tokens": 0,
            "total_tokens": 23,
            "has_tool_calls": False,
            "tool_names": [],
            "elapsed_ms": 10,
            "context_breakdown": {
                "system_prompt_tokens": 3,
                "tools_tokens": 11,
                "conversation_tokens": 7,
                "total_tokens": 21,
                "estimated": True,
                "source": "agentscope_count_tokens",
            },
        }
    )

    assert detail.context_breakdown is not None
    assert detail.context_breakdown.tools_tokens == 11
