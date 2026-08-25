import pytest

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
        "校验目标专家权限",
        status="success",
        execution_time_ms=0,
    )

    assert event["execution_time_ms"] == 1


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
