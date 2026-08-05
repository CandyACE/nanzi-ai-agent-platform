"""会话 MCP 工具与版本 tools 并集。"""

from app.services.ai.session_mcp_tools import (
    apply_session_mcp_tools_to_agent_config,
    extract_session_mcp_tool_names,
    merge_tools_with_session_mcp,
)
from app.schemas.agent import ChatConfig, ToolConfigItem


def test_extract_session_mcp_tool_names_dedupes():
    names = extract_session_mcp_tool_names(
        {
            "mcp_tools": [
                {"id": "1", "name": "mcp_foo"},
                {"id": "2", "name": "mcp_foo"},
                {"id": "3", "name": "mcp_bar"},
                {"name": ""},
                "skip",
            ]
        }
    )
    assert names == ["mcp_foo", "mcp_bar"]


def test_merge_tools_with_session_mcp_unions_and_preserves_config_items():
    configured = [
        "execute_sql_query",
        ToolConfigItem(name="mcp_existing", enabled=True),
    ]
    merged = merge_tools_with_session_mcp(
        configured,
        {
            "mcp_tools": [
                {"id": "a", "name": "mcp_existing"},
                {"id": "b", "name": "mcp_new"},
            ]
        },
    )
    names = [
        item if isinstance(item, str) else item.name
        for item in merged
    ]
    assert names == ["execute_sql_query", "mcp_existing", "mcp_new"]
    assert isinstance(merged[1], ToolConfigItem)


def test_apply_session_mcp_tools_to_agent_config_mutates_tools():
    config = ChatConfig(
        agent_id="a1",
        agent_name="main",
        model_name="m",
        temperature=0.0,
        system_prompt="x",
        tools=["get_current_time"],
    )
    added = apply_session_mcp_tools_to_agent_config(
        config,
        {"mcp_tools": [{"id": "1", "name": "mcp_weather"}]},
    )
    assert added == ["mcp_weather"]
    assert config.tools == ["get_current_time", "mcp_weather"]


def test_apply_session_mcp_tools_noop_without_scope():
    config = ChatConfig(
        agent_id="a1",
        agent_name="main",
        model_name="m",
        temperature=0.0,
        system_prompt="x",
        tools=["a"],
    )
    added = apply_session_mcp_tools_to_agent_config(config, None)
    assert added == []
    assert config.tools == ["a"]
