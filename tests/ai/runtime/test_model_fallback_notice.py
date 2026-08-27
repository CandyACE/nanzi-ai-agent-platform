from types import SimpleNamespace

import pytest

from app.services.ai.runtime.agentscope.event_stream import (
    map_standard_agentscope_event,
)
from app.services.ai.runtime.agentscope.middleware import mark_model_fallback


def test_mark_model_fallback_records_primary_and_selected_model_once():
    primary = SimpleNamespace(model="deepseek-v4-pro")
    fallback = SimpleNamespace(model="gemma-4-31b")
    agent = SimpleNamespace(model=primary)

    info = mark_model_fallback(agent, fallback)

    assert info == {
        "primary_model": "deepseek-v4-pro",
        "fallback_model": "gemma-4-31b",
    }
    assert agent._platform_fallback_info == info

    later = mark_model_fallback(agent, SimpleNamespace(model="another-model"))
    assert later == info


def test_mark_model_fallback_ignores_primary_model_call():
    primary = SimpleNamespace(model="deepseek-v4-pro")
    agent = SimpleNamespace(model=primary)

    assert mark_model_fallback(agent, primary) is None
    assert getattr(agent, "_platform_fallback_info", None) is None


def test_mark_model_fallback_clears_previous_notice_at_next_primary_call():
    primary = SimpleNamespace(model="deepseek-v4-pro")
    fallback = SimpleNamespace(model="gemma-4-31b")
    agent = SimpleNamespace(model=primary)

    mark_model_fallback(agent, fallback)
    assert agent._platform_fallback_info["fallback_model"] == "gemma-4-31b"

    assert mark_model_fallback(agent, primary) is None
    assert getattr(agent, "_platform_fallback_info", None) is None


@pytest.mark.asyncio
async def test_event_mapper_emits_model_fallback_notice_once():
    agent = SimpleNamespace(
        _platform_fallback_info={
            "primary_model": "deepseek-v4-pro",
            "fallback_model": "gemma-4-31b",
        },
    )
    state = {}
    event = SimpleNamespace(type="TEXT_BLOCK_START")

    first = [
        chunk
        async for chunk in map_standard_agentscope_event(
            event,
            state=state,
            agent=agent,
        )
    ]
    second = [
        chunk
        async for chunk in map_standard_agentscope_event(
            event,
            state=state,
            agent=agent,
        )
    ]

    notices = [chunk for chunk in first if chunk.get("type") == "model_fallback"]
    assert notices == [
        {
            "type": "model_fallback",
            "status": "warning",
            "primary_model": "deepseek-v4-pro",
            "fallback_model": "gemma-4-31b",
            "content": (
                "> ⚠️ 主模型 `deepseek-v4-pro` 调用失败，"
                "本次回答由 fallback 模型 `gemma-4-31b` 生成。\n\n"
            ),
        },
    ]
    assert not [chunk for chunk in second if chunk.get("type") == "model_fallback"]
