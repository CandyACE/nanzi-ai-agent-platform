from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure

ROOT = Path(__file__).resolve().parents[2]


def test_agent_tool_timeout_is_ordered_after_iterations_and_uses_stepper():
    source = (ROOT / "frontend/src/views/SystemConfig.vue").read_text(encoding="utf-8")

    assert "agent_max_toolcall_timeout" in source
    order_start = source.index("if (category === 'agent')")
    order_block = source[source.index("const order = [", order_start):]
    assert order_block.index("agent_max_iterations") < order_block.index("agent_max_toolcall_timeout")
    assert "agent_max_toolcall_timeout': '" in source
    assert "'agent_max_toolcall_timeout'" in source
    assert "item.value = String(getAgentToolcallTimeoutValue(item))" in source

    start = source.index("v-else-if=\"item.key === 'agent_max_toolcall_timeout'\"")
    end = source.index("v-else-if=\"['audit_log_retention_days'", start)
    stepper = source[start:end]
    assert "aria-label=\"减少工具调用超时时间\"" in stepper
    assert "aria-label=\"增加工具调用超时时间\"" in stepper
    assert "adjustAgentToolcallTimeout(item, -1)" in stepper
    assert "adjustAgentToolcallTimeout(item, 1)" in stepper
    assert "type=\"number\"" in stepper
    assert "inputmode=\"numeric\"" in stepper
    assert "@keydown=\"handleAgentToolcallTimeoutKeydown\"" in stepper
    assert "@input=\"handleAgentToolcallTimeoutInput(item, $event)\"" in stepper
    assert "@blur=\"normalizeAgentToolcallTimeoutInput(item)\"" in stepper
    assert "min=\"1\"" in stepper
    assert "max=\"3600\"" in stepper
    assert "Math.max(1" in source
    assert "Math.min(3600" in source
    assert "type=\"text\"" not in stepper

    numeric_branch = source[source.index("['audit_log_retention_days'"):source.index("['audit_log_retention_days'") + 420]
    assert "agent_max_toolcall_timeout" not in numeric_branch
