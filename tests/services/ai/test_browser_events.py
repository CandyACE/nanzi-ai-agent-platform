import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from agentscope.permission import PermissionBehavior

from app.core import context as core_context
from app.schemas.browser import BrowserElement, BrowserSnapshot
from app.services.ai.browser.browser_runtime import browser_runtime
from app.services.ai.runtime.agentscope.tools import RuntimeToolSpec
from app.services.ai.runtime.agentscope.tools import _browser_permission_decision
from app.services.ai.runtime.agentscope.browser_events import build_browser_refresh_event
from app.services.ai.runtime.agentscope.browser_events import build_browser_session_event
from app.services.ai.tools.browser_tools import browser_click, browser_fill, browser_open
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


def test_browser_action_result_emits_refresh_event_without_sensitive_output():
    event = build_browser_refresh_event(
        "browser_click",
        '{"session_id":"bs-1","url":"https://www.baidu.com/s?wd=test"}',
    )

    assert event == {
        "type": "browser_refresh",
        "session_id": "bs-1",
    }
    assert build_browser_refresh_event("browser_snapshot", "{}") is None


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


@pytest.mark.asyncio
async def test_browser_fill_allows_sensitive_snapshot_targets(monkeypatch):
    class FakeContext:
        browser_session_id = "bs-1"
        user_id = 1

    snapshot = BrowserSnapshot(
        session_id="bs-1",
        snapshot_id="snap-1",
        url="https://example.com/",
        title="Example",
        elements=[
            BrowserElement(
                ref="e1",
                role="textbox",
                name="验证码",
                sensitive=True,
            )
        ],
    )
    monkeypatch.setattr(core_context, "get_current_agent_context", lambda: FakeContext())
    monkeypatch.setattr(browser_runtime, "cached_snapshot", lambda *_args: snapshot)

    decision = await _browser_permission_decision(
        "browser_fill",
        {"snapshot_id": "snap-1", "target_ref": "e1"},
    )

    assert decision.behavior == PermissionBehavior.ALLOW
    assert decision.decision_reason == "browser_fill_target"


@pytest.mark.asyncio
async def test_stale_browser_click_is_denied_instead_of_asking_for_confirmation(monkeypatch):
    class FakeContext:
        browser_session_id = "bs-1"
        user_id = 1

    monkeypatch.setattr(core_context, "get_current_agent_context", lambda: FakeContext())

    def stale_snapshot(*_args):
        raise ValueError("浏览器快照已过期")

    monkeypatch.setattr(browser_runtime, "cached_snapshot", stale_snapshot)

    decision = await _browser_permission_decision(
        "browser_click",
        {"snapshot_id": "stale-snapshot", "target_ref": "e1"},
    )

    assert decision.behavior == PermissionBehavior.DENY
    assert decision.bypass_immune is True
    assert decision.decision_reason == "browser_target_not_in_snapshot"


def test_browser_open_result_emits_persisted_approval_mode():
    event = build_browser_session_event(
        "browser_open",
        '{"session_id":"bs-1","url":"https://www.baidu.com/","title":"百度",'
        '"approval_mode":"autopilot"}',
    )

    assert event["approval_mode"] == "autopilot"


@pytest.mark.asyncio
async def test_browser_open_result_contains_session_approval_mode(monkeypatch):
    class FakeContext:
        user_id = 1
        conversation_id = "conv-1"

    session = SimpleNamespace(id="bs-1", approval_mode="guarded")
    snapshot = BrowserSnapshot(
        session_id="bs-1",
        snapshot_id="snap-1",
        url="https://www.baidu.com/",
        title="百度",
    )
    monkeypatch.setattr(
        "app.services.ai.tools.browser_tools.get_current_agent_context",
        lambda: FakeContext(),
    )
    monkeypatch.setattr(browser_runtime, "open_for_user", AsyncMock(return_value=session))
    monkeypatch.setattr(browser_runtime, "snapshot", AsyncMock(return_value=snapshot))

    payload = json.loads(await browser_open.ainvoke({}))

    assert payload["approval_mode"] == "guarded"
