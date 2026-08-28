from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure

ROOT = Path(__file__).resolve().parents[2]


def test_version_tool_timeout_is_at_top_of_tools_step_and_supports_inheritance_and_numeric_input():
    source = (ROOT / "frontend/src/components/agent/AgentVersionEditorDrawer.vue").read_text(encoding="utf-8")

    tools_step = source[source.index("versionConfigStep === 'tools'"):]
    timeout_pos = tools_step.index("toolcall_timeout_seconds")
    search_pos = tools_step.index(":value=\"toolSearchQuery\"")
    assert timeout_pos < search_pos
    assert "使用智能体专属配置" in tools_step
    assert "跟随全局配置" in tools_step
    assert "启用后，以当前智能体版本配置为准，不再与全局或工具配置取最大值" in tools_step
    assert "将与全局及工具配置取最长的超时时间" not in tools_step
    assert "type=\"number\"" in tools_step[timeout_pos:search_pos]
    assert "inputmode=\"numeric\"" in tools_step[timeout_pos:search_pos]
    assert "min=\"1\"" in tools_step[timeout_pos:search_pos]
    assert "max=\"86400\"" in tools_step[timeout_pos:search_pos]
    assert "handleAgentVersionToolcallTimeoutKeydown" in source
    assert "handleAgentVersionToolcallTimeoutInput" in source
    assert "normalizeAgentVersionToolcallTimeoutInput" in source


def test_version_form_and_api_carry_nullable_tool_timeout():
    agent_api_source = (ROOT / "frontend/src/api/agent.ts").read_text(encoding="utf-8")
    management_source = (ROOT / "frontend/src/views/AgentManagement.vue").read_text(encoding="utf-8")
    editor_source = (ROOT / "frontend/src/components/agent/AgentVersionEditorDrawer.vue").read_text(encoding="utf-8")

    assert "toolcall_timeout_seconds?: number | null" in agent_api_source
    assert "toolcall_timeout_seconds: null" in management_source
    assert "getGlobalToolcallTimeout" in agent_api_source
    assert "getGlobalToolcallTimeout" in management_source
    assert ':global-agent-toolcall-timeout="globalAgentToolcallTimeout"' in management_source
    assert "globalAgentToolcallTimeout: number" in editor_source
    assert "当前全局配置：{{ globalAgentToolcallTimeout }} 秒" in editor_source
