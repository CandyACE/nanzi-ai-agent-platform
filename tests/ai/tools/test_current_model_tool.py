import json

import pytest

from app.core.context import AgentContext, set_agent_context
from app.services.ai.runtime.agentscope.tools import READ_ONLY_TOOL_NAMES
from app.services.ai.tools.registry import ToolRegistry
from app.services.ai.tools.system_tools import SYSTEM_IMPLICIT_TOOLS, get_current_model


pytestmark = pytest.mark.no_infrastructure


@pytest.mark.asyncio
async def test_get_current_model_returns_request_scoped_public_metadata():
    set_agent_context(
        AgentContext(
            agent_id="agent-1",
            agent_name="general",
            runtime_model_info={
                "configured_model": "团队默认模型",
                "effective_model_id": "deepseek-chat",
                "source": "agent_config",
                "phase": "primary_agent",
                "is_fallback": False,
                "resolution_status": "registry_resolved",
            },
        )
    )

    try:
        result = json.loads(await get_current_model.ainvoke({}))
    finally:
        set_agent_context(None)

    assert result["effective_model_id"] == "deepseek-chat"
    assert result["phase"] == "primary_agent"
    assert "api_key" not in result
    assert "base_url" not in result


@pytest.mark.asyncio
async def test_get_current_model_reports_unavailable_without_request_context():
    set_agent_context(None)

    result = json.loads(await get_current_model.ainvoke({}))

    assert result == {
        "status": "unavailable",
        "reason": "当前请求没有可用的运行时模型信息",
    }


def test_current_model_is_system_implicit_read_only_tool():
    assert get_current_model in SYSTEM_IMPLICIT_TOOLS
    assert "get_current_model" in READ_ONLY_TOOL_NAMES
    assert "get_current_model" in ToolRegistry._registry
    assert get_current_model in ToolRegistry.get_system_implicit_tools()


def test_current_model_runtime_spec_is_read_only():
    from app.services.ai.runtime.agentscope.tools import runtime_tool_spec_from_legacy_tool

    spec = runtime_tool_spec_from_legacy_tool(get_current_model, source_type="system")

    assert spec.permission_scope == "read"
    assert spec.is_read_only is True
