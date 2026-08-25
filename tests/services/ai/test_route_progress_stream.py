import asyncio

import pytest

from app.services.ai.agent_service import AgentService


pytestmark = pytest.mark.no_infrastructure


@pytest.mark.asyncio
async def test_route_progress_is_forwarded_before_resolution_finishes(monkeypatch):
    service = AgentService()
    release = asyncio.Event()
    config = object()

    async def resolve(*, route_progress, **kwargs):
        await route_progress(
            {
                "type": "log",
                "id": "route:candidate_catalog",
                "title": "获取可用专家",
                "category": "router",
                "status": "pending",
            }
        )
        await release.wait()
        return config, None, 1.0, None

    monkeypatch.setattr(service, "_resolve_and_verify_agent", resolve)
    route_events = asyncio.Queue()

    task = service._start_route_resolution(
        route_events=route_events,
        resolve_kwargs={"messages": [], "user_query": "测试"},
    )
    event = await asyncio.wait_for(route_events.get(), timeout=0.1)
    assert event["id"] == "route:candidate_catalog"
    assert event["status"] == "pending"
    assert not task.done()

    release.set()
    result = await task
    assert result[0] is config
    assert result[1:] == (None, 1.0, None)
