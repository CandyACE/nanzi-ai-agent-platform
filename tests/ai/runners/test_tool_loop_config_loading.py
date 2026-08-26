import asyncio

import pytest

from app.services.ai.runners.assistant_agent_runner import AssistantAgentRunner


pytestmark = pytest.mark.no_infrastructure


@pytest.mark.asyncio
async def test_tool_loop_detector_loads_config_values_concurrently(monkeypatch):
    active = 0
    max_active = 0
    values = {
        "agent_tool_loop_detection_enabled": "true",
        "agent_tool_loop_fuse_threshold": "4",
        "agent_tool_loop_ping_pong_threshold": "5",
        "agent_tool_loop_global_limit": "12",
    }

    async def fake_get(key, default=None):
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0)
        active -= 1
        return values.get(key, default)

    monkeypatch.setattr(
        "app.services.config_service.ConfigService.get",
        fake_get,
    )

    detector = await AssistantAgentRunner._create_tool_loop_detector()

    assert max_active == 4
    assert detector.enabled is True
    assert detector.threshold == 4
    assert detector.ping_pong_threshold == 5
    assert detector.global_limit == 12
