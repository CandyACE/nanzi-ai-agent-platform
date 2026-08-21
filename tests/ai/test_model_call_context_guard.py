from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services.ai.runtime.agentscope.middleware import ModelCallStatsMiddleware


pytestmark = pytest.mark.no_infrastructure


@pytest.mark.asyncio
async def test_model_call_guard_clamps_completion_to_remaining_context():
    parameters = SimpleNamespace(max_tokens=32768)
    current_model = SimpleNamespace(
        model="deepseek-v3.2",
        context_size=65536,
        parameters=parameters,
        count_tokens=AsyncMock(return_value=65000),
    )
    observed = []

    async def next_handler(**kwargs):
        del kwargs
        observed.append(parameters.max_tokens)
        return SimpleNamespace(
            usage=SimpleNamespace(input_tokens=65000, output_tokens=536),
            content=[],
        )

    middleware = ModelCallStatsMiddleware(
        user_id="u1",
        conversation_id="c1",
        agent_name="main",
        physical_window=65536,
        history_budget=24576,
        completion_reserve=32768,
    )

    with patch(
        "app.services.ai.runtime.agentscope.middleware._append_stat_to_redis",
        new=AsyncMock(),
    ):
        await middleware.on_model_call(
            agent=SimpleNamespace(),
            input_kwargs={
                "current_model": current_model,
                "messages": [],
                "tools": [],
            },
            next_handler=next_handler,
        )

    assert observed == [536]
    assert parameters.max_tokens == 32768
