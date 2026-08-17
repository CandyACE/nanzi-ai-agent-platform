import pytest

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
