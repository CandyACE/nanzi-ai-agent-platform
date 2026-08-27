from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
pytestmark = pytest.mark.no_infrastructure


def test_chat_run_status_route_is_authenticated_and_does_not_use_database():
    source = (ROOT / "app/api/v1/endpoints/chat.py").read_text(encoding="utf-8")
    assert '"/conversation/{conversation_id}/run-status"' in source
    route_start = source.index('"/conversation/{conversation_id}/run-status"')
    route_body = source[route_start:]
    assert "Depends(require_api_key)" in route_body
    assert "conversation_run_lane.get_status" in route_body
    assert "StandardResponse" in route_body
    assert "get_db_session" not in route_body[:route_body.index("async def", 0)]
