import pytest

from app.services.ai.runtime.agentscope.tools import RuntimeToolSpec
from app.services.ai.runtime.agentscope.browser_events import build_browser_session_event
from app.services.ai.tools.browser_tools import browser_click, browser_fill
from app.services.ai.tools.registry import ToolRegistry


pytestmark = pytest.mark.no_infrastructure


def test_browser_open_result_emits_session_event_without_viewer_token():
    event = build_browser_session_event(
        "browser_open",
        '{"session_id":"bs-1","url":"https://www.baidu.com/","title":"百度"}',
    )
    assert event == {
        "type": "browser_session",
        "session_id": "bs-1",
        "url": "https://www.baidu.com/",
        "title": "百度",
    }


def test_non_browser_tool_does_not_emit_browser_event():
    assert build_browser_session_event("browser_snapshot", "{}") is None


def test_browser_tools_are_implicit_first_party_agent_tools():
    names = {getattr(tool, "name", "") for tool in ToolRegistry.get_system_implicit_tools()}
    assert {"browser_open", "browser_snapshot", "browser_click", "browser_fill"}.issubset(names)


def test_browser_tools_do_not_expose_confirmation_or_sensitive_override():
    assert "confirmed" not in browser_click.args_schema.model_fields
    assert "sensitive" not in browser_fill.args_schema.model_fields


@pytest.mark.asyncio
async def test_runtime_tool_audit_redacts_browser_fill_value():
    events = []
    spec = RuntimeToolSpec(
        name="browser_fill",
        description="test",
        parameters_schema={"type": "object"},
        source_type="system",
        callable=lambda **kwargs: {"ok": True},
        audit_callback=events.append,
    )

    await spec.invoke({"target_ref": "e1", "value": "secret", "sensitive": False})

    assert len(events) == 2
    assert all(event.arguments["value"] == "<redacted>" for event in events)
