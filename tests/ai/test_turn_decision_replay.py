import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.schemas.agent import ChatConfig
from app.services.ai.dispatcher import AgentDispatcher
from app.services.ai.executors.assistant_executor import AssistantExecutor
from app.services.ai.executors.data_executor import DataQueryExecutor
from app.services.ai.executors.knowledge_executor import KnowledgeExecutor
from app.services.ai.runners.chatbi.repair_controller import ChatBIRepairController
from app.services.ai.runners.chatbi.run_state import DataRunState
from app.services.ai.runners.chatbi.sql_result_compact import (
    should_rescue_sql_without_followup_content,
)
from app.services.ai.subagent_protocol import (
    SubAgentRequest,
    SubAgentResult,
    SubAgentResultStatus,
)
from app.services.ai.tool_policy import resolve_tool_metadata
from app.services.ai.turn_decision import TurnDecision


pytestmark = pytest.mark.no_infrastructure


CASES = json.loads(
    (
        Path(__file__).parent / "fixtures" / "turn_decision_cases.json"
    ).read_text(encoding="utf-8")
)


def _config(case: dict) -> ChatConfig:
    config = case["config"]
    return ChatConfig(
        agent_id=f"replay-{case['name']}",
        agent_name=case["name"],
        model_name="replay-model",
        temperature=0.0,
        system_prompt="replay",
        tools=config["tools"],
        capabilities=config["capabilities"],
        engine_type="LOCAL",
        engine_config=config["engine_config"],
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
async def test_replay_cases_preserve_executor_and_decision_contract(case: dict):
    config = _config(case)
    decision = TurnDecision.model_validate(case["decision"])
    executor = await AgentDispatcher.dispatch(
        config,
        user_query="replay query",
        messages=[{"role": "user", "content": "replay query"}],
        trace_id=f"trace-{case['name']}",
        trace_buffer=[],
        turn_decision=decision,
    )

    executor_name = {
        AssistantExecutor: "assistant",
        DataQueryExecutor: "data",
        KnowledgeExecutor: "knowledge",
    }[type(executor)]
    expected = case["expected"]
    assert executor_name == expected["executor"]

    assert decision.turn_kind == expected["turn_kind"]

    if "tool" in case:
        metadata = resolve_tool_metadata(SimpleNamespace(name=case["tool"]))
        for field in ("tool_capability", "tool_confirmation"):
            expected_value = expected.get(field)
            if expected_value is not None:
                actual_field = "capability" if field == "tool_capability" else "confirmation"
                assert getattr(metadata, actual_field) == expected_value


def test_replay_sql_repair_and_final_synthesis_cases():
    repair_case = next(case for case in CASES if case["name"] == "sql_repair")
    repair_state = DataRunState(
        requires_fresh_data=True,
        requires_sql_query=True,
        sql_before_schema=True,
    )
    repair = ChatBIRepairController(repair_state).decide()
    assert repair is not None
    assert repair.kind == repair_case["repair"]["kind"]
    assert repair.tool_choice.mode == repair_case["repair"]["tool"]

    synthesis_case = next(case for case in CASES if case["name"] == "final_synthesis")
    response = synthesis_case["response"]
    synthesis_state = SimpleNamespace(
        empty_sql_result=False,
        diagnostic_sql_pending_final=False,
        has_successful_nonempty_sql=True,
        last_successful_sql_output='{"items":[[1]]}',
        sql_repeat_gate_block=False,
        deferred_continue_query=False,
        last_successful_nonempty_sql_at=response["last_sql_at"],
        last_visible_content_at=response["last_content_at"],
    )
    phase = (
        "final_synthesis"
        if should_rescue_sql_without_followup_content(synthesis_state)
        else "stream_finalize"
    )
    assert phase == synthesis_case["expected"]["response_phase"]


def test_replay_subagent_protocol_keeps_request_metadata_and_result_status():
    case = next(case for case in CASES if case["name"] == "subagent_delegation")
    request = SubAgentRequest(
        target_agent_name="data-agent",
        query="查询本月订单",
        caller_agent_id="main-agent",
        caller_agent_name="main",
    )
    result = SubAgentResult(
        status=SubAgentResultStatus.COMPLETED,
        target_agent_id="data-agent-id",
        target_agent_name=request.target_agent_name,
        content="已完成查询",
    )

    assert case["expected"]["subagent_status"] == result.to_metadata()["status"]
    assert request.to_metadata()["query_chars"] == len(request.query)
    assert result.to_tool_text() == "已完成查询"
