import pytest

from app.services.ai.browser.browser_policy import (
    BrowserUrlBlocked,
    classify_browser_action,
    decide_browser_action,
    redact_browser_arguments,
    validate_browser_navigation,
    validate_browser_request,
)


pytestmark = pytest.mark.no_infrastructure


def test_guarded_blocks_submit_and_allows_search_click():
    assert classify_browser_action(role="button", name="百度一下") == "interact"
    assert classify_browser_action(role="button", name="提交订单") == "commit"
    assert decide_browser_action("guarded", "interact").allowed is True
    assert decide_browser_action("guarded", "commit").requires_confirmation is True


def test_navigation_rejects_private_and_metadata_addresses():
    with pytest.raises(BrowserUrlBlocked):
        validate_browser_navigation("http://127.0.0.1:8000/")
    with pytest.raises(BrowserUrlBlocked):
        validate_browser_navigation("http://169.254.169.254/latest/meta-data/")
    # Fake-IP 网段 (Clash / Surge / Sing-box TUN 模式) 允许正常导航
    assert validate_browser_navigation("http://198.18.0.22/") == "http://198.18.0.22/"


def test_request_guard_covers_websocket_and_rejects_unsafe_protocols():
    with pytest.raises(BrowserUrlBlocked):
        validate_browser_request("ws://127.0.0.1:9222/devtools/browser")
    with pytest.raises(BrowserUrlBlocked):
        validate_browser_request("javascript:alert(1)")
    assert validate_browser_request("data:text/plain,ok") == "data:text/plain,ok"


def test_sensitive_fill_is_redacted_from_audit_payload():
    payload = redact_browser_arguments({"value": "secret", "sensitive": True})
    assert payload["value"] == "<redacted>"
