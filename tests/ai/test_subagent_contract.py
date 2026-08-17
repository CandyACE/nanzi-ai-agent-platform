import pytest

import app.services.ai.subagent_protocol as subagent_protocol

from app.services.ai.subagent_protocol import (
    EMPTY_SUB_AGENT_RESULT_MESSAGE,
    SubAgentRequest,
    SubAgentResult,
    SubAgentResultStatus,
)


pytestmark = pytest.mark.no_infrastructure


def test_subagent_request_metadata_excludes_raw_query_and_credentials():
    request = SubAgentRequest(
        target_agent_name="data-agent",
        query="查询本月订单",
        caller_agent_id="main",
        approval_mode="ask",
    )

    metadata = request.to_metadata()

    assert metadata["query_chars"] == len(request.query)
    assert "query" not in metadata
    assert "api_key" not in metadata


def test_subagent_request_metadata_keeps_run_controls_without_raw_values():
    request = SubAgentRequest(
        target_agent_name="knowledge-agent",
        query="如何开启辅助驾驶",
        caller_agent_id="main",
        run_id="run-123",
        parent_trace_id="trace-main",
        max_depth=1,
        tool_filter=["search_knowledge_base"],
        output_schema={"type": "object", "properties": {"answer": {"type": "string"}}},
    )

    metadata = request.to_metadata()

    assert metadata["run_id"] == "run-123"
    assert metadata["parent_trace_id"] == "trace-main"
    assert metadata["max_depth"] == 1
    assert metadata["tool_filter"] == ["search_knowledge_base"]
    assert metadata["output_schema"] == {"type": "object", "property_count": 1}
    assert "如何开启辅助驾驶" not in str(metadata)


def test_subagent_result_exposes_stop_reason_lineage_and_structured_output():
    result = SubAgentResult(
        status=SubAgentResultStatus.COMPLETED,
        stop_reason="completed",
        run_id="run-123",
        parent_trace_id="trace-main",
        child_trace_id="trace-child",
        structured={"answer": "请在车辆设置中开启"},
        content="请在车辆设置中开启",
    )

    metadata = result.to_metadata()

    assert metadata["run_id"] == "run-123"
    assert metadata["parent_trace_id"] == "trace-main"
    assert metadata["child_trace_id"] == "trace-child"
    assert metadata["stop_reason"] == "completed"
    assert metadata["structured"] is True


def test_subagent_result_derives_stop_reason_for_legacy_status():
    result = SubAgentResult(status=SubAgentResultStatus.TIMEOUT, content="超时")

    assert result.to_metadata()["stop_reason"] == "timeout"


def test_validate_structured_output_accepts_matching_object_schema():
    valid, reason = getattr(subagent_protocol, "validate_structured_output", lambda *_: (False, "missing"))(
        {"answer": "已完成", "confidence": 0.9},
        {
            "type": "object",
            "properties": {
                "answer": {"type": "string"},
                "confidence": {"type": "number"},
            },
            "required": ["answer"],
            "additionalProperties": False,
        },
    )

    assert valid is True
    assert reason is None


def test_validate_structured_output_rejects_schema_mismatch():
    valid, reason = getattr(subagent_protocol, "validate_structured_output", lambda *_: (False, "missing"))(
        {"answer": 123},
        {
            "type": "object",
            "properties": {"answer": {"type": "string"}},
            "required": ["answer"],
        },
    )

    assert valid is False
    assert reason == "property 'answer' must be a string"


def test_validate_structured_schema_rejects_non_object_root():
    from app.services.ai.subagent_protocol import validate_structured_schema

    assert validate_structured_schema({"type": "array"}) == "schema root must be an object"


@pytest.mark.parametrize(
    "status,content,expected",
    [
        (SubAgentResultStatus.EMPTY, "", EMPTY_SUB_AGENT_RESULT_MESSAGE),
        (SubAgentResultStatus.TIMEOUT, "超时", "超时"),
        (SubAgentResultStatus.FAILED, "失败", "失败"),
    ],
)
def test_subagent_result_keeps_model_facing_text_compatible(status, content, expected):
    result = SubAgentResult(status=status, content=content)

    assert result.to_tool_text() == expected
    assert result.to_metadata()["status"] == status.value
