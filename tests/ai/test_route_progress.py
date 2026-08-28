import asyncio

import pytest

from app.services.ai.agent_service import AgentService
from app.services.ai.route_progress import build_route_stage_log


pytestmark = pytest.mark.no_infrastructure


def test_route_stage_log_uses_stable_id_and_safe_fields():
    event = build_route_stage_log(
        "candidate_catalog",
        "获取可用专家",
        status="pending",
    )

    assert event == {
        "type": "log",
        "id": "route:candidate_catalog",
        "title": "获取可用专家",
        "category": "router",
        "status": "pending",
    }
    assert "thought" not in event
    assert "candidates" not in event


def test_route_stage_log_keeps_same_id_for_completion_and_duration():
    event = build_route_stage_log(
        "candidate_catalog",
        "获取可用专家",
        status="success",
        execution_time_ms=12.5,
        details="已完成授权范围检查",
    )

    assert event["id"] == "route:candidate_catalog"
    assert event["status"] == "success"
    assert event["execution_time_ms"] == 12.5
    assert event["details"] == "已完成授权范围检查"


def test_route_stage_log_normalizes_sub_millisecond_duration_for_display():
    event = build_route_stage_log(
        "target_permission",
        "校验入口专家权限",
        status="success",
        execution_time_ms=0,
    )

    assert event["execution_time_ms"] == 1


@pytest.mark.asyncio
async def test_entry_config_and_permission_events_are_preparation_siblings():
    service = AgentService()
    route_events = asyncio.Queue()

    async def fake_resolve(**kwargs):
        progress = kwargs["route_progress"]
        await progress(build_route_stage_log("target_config", "加载入口专家配置", status="pending"))
        await progress(build_route_stage_log("target_permission", "校验入口专家权限", status="pending"))
        return None

    service._resolve_and_verify_agent = fake_resolve
    task = service._start_route_resolution(route_events=route_events, resolve_kwargs={})
    await task

    events = [await route_events.get() for _ in range(2)]
    assert [event["parent_id"] for event in events] == [
        "preparation:auth_context_capability",
        "preparation:auth_context_capability",
    ]


@pytest.mark.asyncio
async def test_emit_route_stage_forwards_only_route_log_payload():
    received = []

    async def receive(event):
        received.append(event)

    from app.services.ai.route_progress import emit_route_stage

    await emit_route_stage(receive, "router_model", "匹配目标专家", status="pending")

    assert received == [
        {
            "type": "log",
            "id": "route:router_model",
            "title": "匹配目标专家",
            "category": "router",
            "status": "pending",
        }
    ]
