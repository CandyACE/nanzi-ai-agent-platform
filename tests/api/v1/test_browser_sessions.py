from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from collections import deque

import pytest
from starlette.requests import Request

from app.api.v1.api import v1_router, v1_secured
from app.api.v1.endpoints.browser import _accept_viewer_message
from app.api.v1.endpoints.browser import _viewer_origin_allowed
from app.api.v1.endpoints.browser import get_browser_screenshot
from app.schemas.browser import BrowserProfileResponse, BrowserSessionResponse, BrowserSnapshot


pytestmark = pytest.mark.no_infrastructure


def _mounted_paths(router, prefix=""):
    paths = set()
    for route in router.routes:
        include_context = getattr(route, "include_context", None)
        if include_context is not None:
            nested_prefix = f"{prefix}{include_context.prefix}".rstrip("/")
            paths.update(_mounted_paths(include_context.included_router, nested_prefix))
            continue

        path = getattr(route, "path", None)
        if path is not None:
            paths.add(f"{prefix}{path}" or "/")
    return paths


def test_browser_routes_are_mounted_under_secured_chat_prefix():
    paths = _mounted_paths(v1_secured)
    assert "/chat/browser/sessions/open" in paths
    assert "/chat/browser/sessions/active" in paths
    assert "/chat/browser/sessions/{session_id}/policy" in paths
    assert "/chat/browser/sessions/{session_id}/detach" in paths
    assert "/chat/browser/sessions/{session_id}" in paths
    viewer_paths = _mounted_paths(v1_router)
    assert "/chat/browser/sessions/{session_id}/viewer" in viewer_paths
    assert "/chat/browser/sessions/{session_id}/screenshot" in viewer_paths


def test_browser_environment_install_route_is_admin_only_and_streams_logs():
    source = (Path(__file__).resolve().parents[3] / "app/api/v1/endpoints/browser.py").read_text(encoding="utf-8")
    assert '"/environment/install/stream"' in source
    assert "Depends(require_admin)" in source
    assert "StreamingResponse" in source
    assert "create_subprocess_exec" in source
    assert "_browser_install_commands" in source
    assert '"pip", "install", "--python"' in source
    assert "shutil.which(\"uv\")" in source
    assert '"-m", "playwright", "install", "chromium"' in source
    assert '"text/event-stream"' in source


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


def test_browser_viewer_updates_session_activity_for_semantic_actions():
    source = (Path(__file__).resolve().parents[3] / "app/api/v1/endpoints/browser.py").read_text(encoding="utf-8")
    assert source.count("session.updated_at = datetime.now()") >= 2


def test_browser_viewer_exposes_human_control_handoff_and_captcha_events():
    source = (Path(__file__).resolve().parents[3] / "app/api/v1/endpoints/browser.py").read_text(encoding="utf-8")
    assert "control_state" in source
    assert "release_control" in source
    assert '"type": "captcha"' in source


def test_browser_viewer_releases_human_control_for_all_disconnect_paths():
    source = (Path(__file__).resolve().parents[3] / "app/api/v1/endpoints/browser.py").read_text(encoding="utf-8")
    assert "should_release_control = False" in source
    assert "viewer_connection_id = uuid.uuid4().hex" in source
    assert "owner_id=viewer_connection_id" in source
    assert "if should_release_control:" in source
    assert "finally:" in source
    assert "await browser_runtime.release_human_control(" in source


def test_browser_viewer_allows_same_origin_and_rejects_unconfigured_origin():
    same_origin = SimpleNamespace(
        headers={"origin": "https://example.com", "host": "example.com"}
    )
    cross_origin = SimpleNamespace(
        headers={"origin": "https://evil.example", "host": "example.com"}
    )

    assert _viewer_origin_allowed(same_origin) is True
    assert _viewer_origin_allowed(cross_origin) is False


def test_browser_viewer_rejects_oversized_and_flooded_messages():
    timestamps = deque()

    accepted, reason = _accept_viewer_message({"type": "snapshot"}, timestamps, now=100.0)
    assert accepted is True
    assert reason is None

    oversized, oversized_reason = _accept_viewer_message(
        {"type": "text", "value": "x" * 70000}, timestamps, now=100.1
    )
    assert oversized is False
    assert "消息过大" in oversized_reason

    for index in range(119):
        accepted, _ = _accept_viewer_message({"type": "snapshot"}, timestamps, now=101.0 + index / 100)
        assert accepted is True
    flooded, flooded_reason = _accept_viewer_message(
        {"type": "snapshot"}, timestamps, now=102.5
    )
    assert flooded is False
    assert "频繁" in flooded_reason


def test_browser_viewer_allows_high_frequency_mouse_move_stream():
    timestamps = deque()
    mouse_move_timestamps = deque()

    for index in range(200):
        accepted, reason = _accept_viewer_message(
            {"type": "mouse_move", "x": index, "y": index},
            timestamps,
            mouse_move_timestamps=mouse_move_timestamps,
            now=100.0 + index / 60,
        )
        assert accepted is True
        assert reason is None

    assert len(timestamps) == 0
    assert len(mouse_move_timestamps) == 200


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
