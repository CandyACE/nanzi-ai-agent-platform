import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


pytestmark = pytest.mark.no_infrastructure


def test_execution_performance_tracker_records_stage_and_ttft():
    from app.services.ai.runtime.execution_observability import (
        ExecutionPerformanceTracker,
    )

    ticks = iter([10.0, 10.1, 10.25, 10.5, 10.6])
    tracker = ExecutionPerformanceTracker(clock=lambda: next(ticks))

    tracker.mark("route_resolution")
    tracker.observe_chunk({"type": "log", "content": "not an answer"})
    tracker.observe_chunk({"type": "answer_delta", "content": "第一段"})
    tracker.mark("executor_finish")

    result = tracker.snapshot(
        trace_buffer=[
            SimpleNamespace(event_type="thought"),
            SimpleNamespace(event_type="model_call"),
            SimpleNamespace(event_type="tool_call"),
        ],
        status="success",
    )

    assert result["stages_ms"] == {
        "route_resolution": 100.0,
        "executor_finish": 500.0,
    }
    assert result["ttft_ms"] == 250.0
    assert result["model_call_count"] == 2
    assert result["tool_call_count"] == 1
    assert result["status"] == "success"
    assert "第一段" not in result


def test_execution_performance_tracker_ignores_control_events_for_ttft():
    from app.services.ai.runtime.execution_observability import (
        ExecutionPerformanceTracker,
    )

    ticks = iter([2.0, 2.4, 2.4])
    tracker = ExecutionPerformanceTracker(clock=lambda: next(ticks))

    tracker.observe_chunk({"type": "reasoning_content", "content": "内部推理"})
    tracker.observe_chunk({"type": "log", "content": "正在处理"})
    tracker.observe_chunk({"content": "最终回答"})

    result = tracker.snapshot(trace_buffer=[], status="success")

    assert result["ttft_ms"] == 400.0
    assert result["total_elapsed_ms"] == 400.0


@pytest.mark.asyncio
async def test_agent_service_publishes_execution_performance_snapshot(monkeypatch):
    from app.schemas.agent import ChatConfig
    from app.services.ai.agent_service import AgentService
    from app.services.ai.config import RuntimeModelInfo

    config = ChatConfig(
        agent_id="agent-1",
        agent_name="main",
        model_name="configured-model",
        temperature=0.0,
        system_prompt="test",
        tools=[],
        capabilities=["general_chat"],
    )
    runtime_info = RuntimeModelInfo(
        configured_model="configured-model",
        effective_model_id="effective-model",
        source="test",
    )

    async def route_result():
        return config, None, 1.0, None

    route_task = asyncio.create_task(route_result())
    service = AgentService()

    async def fail_fixed_polling(*_args, **_kwargs):
        raise AssertionError("route resolution should not use fixed-interval polling")

    monkeypatch.setattr(asyncio, "wait_for", fail_fixed_polling)
    monkeypatch.setattr(
        service,
        "_start_route_resolution",
        lambda **_kwargs: route_task,
    )
    monkeypatch.setattr(
        "app.services.ai.session_mcp_tools.apply_session_mcp_tools_to_agent_config",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        service,
        "_resolve_runtime_model_info_safe",
        AsyncMock(return_value=runtime_info),
    )
    monkeypatch.setattr(
        "app.services.ai.agent_service.looks_like_current_model_query",
        lambda _query: True,
    )
    audit = AsyncMock()
    monkeypatch.setattr(
        "app.services.ai.agent_service.AuditManager.log_transaction",
        audit,
    )

    shared_state = {
        "agent_config": None,
        "execution_status": "success",
        "process_timeline": [],
    }
    events = [
        event
        async for event in service._run_chat_turn_stream(
            messages=[{"role": "user", "content": "当前模型是什么"}],
            user_query="当前模型是什么",
            agent_id=None,
            agent_name=None,
            version_id=None,
            conversation_id=None,
            user_info=None,
            api_key=None,
            enable_multi_agent=False,
            debug_options=None,
            permission_options=None,
            knowledge_dataset_ids=None,
            metadata_dataset_ids=None,
            trace_id="trace-observe",
            trace_buffer=[],
            start_time=asyncio.get_running_loop().time(),
            shared_state=shared_state,
        )
    ]

    snapshot = shared_state["execution_performance"]
    assert events[-1]["content"]
    assert "route_resolution" in snapshot["stages_ms"]
    assert "runtime_model_metadata" in snapshot["stages_ms"]
    assert snapshot["ttft_ms"] is not None
    assert snapshot["model_call_count"] == 0
    assert snapshot["tool_call_count"] == 0
    assert snapshot["audit_completed"] is True
    assert "content" not in snapshot
    audit.assert_awaited_once()
