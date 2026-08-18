from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from starlette.requests import Request

from app.api.v1.api import v1_router, v1_secured
from app.api.v1.endpoints.browser import get_browser_screenshot
from app.schemas.browser import BrowserProfileResponse, BrowserSessionResponse, BrowserSnapshot


pytestmark = pytest.mark.no_infrastructure


def test_browser_routes_are_mounted_under_secured_chat_prefix():
    paths = {route.path for route in v1_secured.routes}
    assert "/chat/browser/sessions/open" in paths
    assert "/chat/browser/sessions/active" in paths
    assert "/chat/browser/sessions/{session_id}/policy" in paths
    assert "/chat/browser/sessions/{session_id}/detach" in paths
    assert "/chat/browser/sessions/{session_id}" in paths
    viewer_paths = {route.path for route in v1_router.routes}
    assert "/chat/browser/sessions/{session_id}/viewer" in viewer_paths
    assert "/chat/browser/sessions/{session_id}/screenshot" in viewer_paths


def test_browser_public_response_models_do_not_expose_storage_or_token_fields():
    assert "encrypted_storage_ref" not in BrowserProfileResponse.model_fields
    assert "viewer_token_hash" not in BrowserSessionResponse.model_fields


def test_browser_viewer_exposes_human_only_drag_events():
    source = (Path(__file__).resolve().parents[3] / "app/api/v1/endpoints/browser.py").read_text(encoding="utf-8")
    assert '"mouse_down"' in source
    assert '"mouse_move"' in source
    assert '"mouse_up"' in source


def test_browser_viewer_reports_manual_input_focus_after_click():
    source = (Path(__file__).resolve().parents[3] / "app/api/v1/endpoints/browser.py").read_text(encoding="utf-8")
    assert "focused_input" in source
    assert '"type": "focus"' in source


def test_browser_viewer_exposes_human_control_handoff_and_captcha_events():
    source = (Path(__file__).resolve().parents[3] / "app/api/v1/endpoints/browser.py").read_text(encoding="utf-8")
    assert "control_state" in source
    assert "release_control" in source
    assert '"type": "captcha"' in source


@pytest.mark.asyncio
async def test_screenshot_endpoint_reuses_requested_snapshot_without_rereading_page(tmp_path: Path):
    screenshot_path = tmp_path / "snapshot.png"
    screenshot_path.write_bytes(b"png")
    snapshot = BrowserSnapshot(
        session_id="session-1",
        snapshot_id="snapshot-1",
        url="https://www.baidu.com/",
        title="百度",
        screenshot_ref=str(screenshot_path),
    )
    runtime = SimpleNamespace(
        has_session=Mock(return_value=True),
        cached_snapshot=Mock(return_value=snapshot),
        snapshot=AsyncMock(),
    )
    db = AsyncMock()
    session_context = Mock()
    session_context.__aenter__ = AsyncMock(return_value=db)
    session_context.__aexit__ = AsyncMock(return_value=False)
    owned_session = SimpleNamespace(id="session-1")
    session_service = Mock()
    session_service.resolve_viewer_token = AsyncMock(return_value=owned_session)

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/chat/browser/sessions/session-1/screenshot",
            "headers": [],
            "query_string": b"snapshot_id=snapshot-1",
        }
    )

    with patch("app.api.v1.endpoints.browser.AsyncSessionLocal", return_value=session_context), \
        patch("app.api.v1.endpoints.browser.BrowserSessionService", return_value=session_service), \
        patch("app.api.v1.endpoints.browser.browser_runtime", runtime):
        response = await get_browser_screenshot(
            "session-1",
            request,
            token="viewer-token-12345678901234567890",
            snapshot_id="snapshot-1",
        )

    assert response.path == str(screenshot_path)
    runtime.cached_snapshot.assert_called_once_with("session-1", "snapshot-1")
    runtime.snapshot.assert_not_awaited()
