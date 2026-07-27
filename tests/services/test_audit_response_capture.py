import gzip

import pytest

from app.core.middleware import _decode_captured_response_body
from app.services.audit_service import _sanitize_text_field
from app.services.audit_service import AuditService


pytestmark = pytest.mark.no_infrastructure


def test_decode_captured_gzip_json_response_before_audit_storage():
    body = gzip.compress(b'{"code": 0, "data": {"ok": true}}')

    result = _decode_captured_response_body(
        body,
        content_encoding="gzip",
        content_type="application/json",
    )

    assert result == '{"code": 0, "data": {"ok": true}}'
    assert "\x00" not in result


def test_decode_captured_binary_response_returns_safe_summary():
    result = _decode_captured_response_body(
        b"\x00\x01\x02binary",
        content_encoding=None,
        content_type="application/octet-stream",
    )

    assert result == "<binary response: 9 bytes>"
    assert "\x00" not in result


def test_sanitize_text_field_removes_postgresql_unsupported_nul_bytes():
    assert _sanitize_text_field("prefix\x00suffix") == "prefixsuffix"


@pytest.mark.asyncio
async def test_audit_request_data_truncates_large_response_before_enqueue(monkeypatch):
    captured = []

    async def capture(log_data):
        captured.append(log_data)

    monkeypatch.setattr(AuditService, "enqueue_log", capture)

    await AuditService.log_request_data(
        trace_id="trace-large-response",
        user_name="admin",
        endpoint="/api/portal/agents",
        method="GET",
        status_code=200,
        process_time_ms=1.0,
        client_ip="127.0.0.1",
        response_body="智能体列表" * 20000,
    )

    response_body = captured[0]["response_body"]
    assert len(response_body.encode("utf-8")) <= 10 * 1024
    assert response_body.endswith("...(truncated)")
