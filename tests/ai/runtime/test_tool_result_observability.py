from types import SimpleNamespace

import pytest

from app.services.ai.runtime.agentscope.tool_result import (
    extract_tool_result_error_reason,
    is_tool_result_error,
)
from app.services.ai.runtime.agentscope.stream_reconcile import truncate_for_display
from app.services.ai.runners.assistant_agent_runner import AssistantAgentRunner


pytestmark = pytest.mark.no_infrastructure


def _runner_for_observation() -> AssistantAgentRunner:
    runner = object.__new__(AssistantAgentRunner)
    runner.config = SimpleNamespace(
        agent_name="Assistant",
        model_name="test-model",
        temperature=0.0,
    )
    runner.step_counter = 1
    return runner


def test_successful_bash_output_containing_error_is_not_a_failure():
    assert is_tool_result_error(
        "Bash",
        "grep found the word Error in the file",
        result_state="success",
    ) is False

    result = _runner_for_observation()._build_tool_observation(
        tool_id="bash-1",
        tool_name="Bash",
        tool_args={"command": "grep Error app.log"},
        tool_output="grep found the word Error in the file",
        duration_tool=12,
        target_tool=None,
        tool_index=0,
        tool_result_state="success",
    )

    assert result["log"]["status"] == "success"
    assert "error_reason" not in result["log"]

    assert is_tool_result_error("bash", "Command failed: exit 1") is True


def test_failed_bash_exposes_a_sanitized_concrete_reason():
    output = "Command failed: cat /Users/demo/secret.txt\n\nStderr:\nPermission denied"

    assert is_tool_result_error("Bash", output, result_state="error") is True
    assert extract_tool_result_error_reason(
        "Bash",
        output,
        result_state="error",
    ) == "Permission denied"

    result = _runner_for_observation()._build_tool_observation(
        tool_id="bash-2",
        tool_name="Bash",
        tool_args={"command": "cat /Users/demo/secret.txt"},
        tool_output=output,
        duration_tool=12,
        target_tool=None,
        tool_index=0,
        tool_result_state="error",
    )

    assert result["log"]["status"] == "error"
    assert result["log"]["error_reason"] == "Permission denied"
    assert "/Users/demo" not in result["log"]["error_reason"]


def test_tool_log_truncation_is_labeled_as_display_preview():
    preview = truncate_for_display("x" * 20, max_len=10)

    assert preview.endswith("… [日志预览已截断]")


def test_failed_bash_without_stderr_does_not_echo_the_command():
    output = "Command failed: curl -H 'Authorization: Bearer secret-token' https://internal.example"

    assert extract_tool_result_error_reason(
        "Bash",
        output,
        result_state="error",
    ) == "命令执行失败（退出码非 0）"
