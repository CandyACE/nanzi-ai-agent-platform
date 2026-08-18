import pytest

from app.api.v1.api import v1_router, v1_secured
from app.schemas.browser import BrowserProfileResponse, BrowserSessionResponse


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
