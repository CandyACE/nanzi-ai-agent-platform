import json

import pytest

from app.services.ai.audit_payload import bound_audit_payload


pytestmark = pytest.mark.no_infrastructure


def test_small_payload_keeps_json_shape_and_does_not_share_mutable_objects():
    source = {"rows": [{"name": "张三"}], "count": 1}

    result = bound_audit_payload(source, max_bytes=1024)

    assert result == source
    assert result is not source
    result["rows"][0]["name"] = "李四"
    assert source["rows"][0]["name"] == "张三"


def test_large_payload_becomes_bounded_preview_with_original_size_metadata():
    source = {"content": "结果" * 20_000}

    result = bound_audit_payload(source, max_bytes=1024)
    encoded = json.dumps(result, ensure_ascii=False).encode("utf-8")

    assert len(encoded) <= 1024
    assert result["__audit_trace"]["truncated"] is True
    assert result["__audit_trace"]["original_bytes"] > 1024
    assert result["__audit_trace"]["max_bytes"] == 1024
    assert isinstance(result["preview"], str)


def test_utf8_truncation_never_returns_invalid_json_or_mutates_source():
    source = {"content": "😀" * 100}
    before = source["content"]

    result = bound_audit_payload(source, max_bytes=256)

    json.dumps(result, ensure_ascii=False)
    assert source["content"] == before


def test_large_structured_payload_is_bounded_for_audit():
    source = {
        "columns": ["name"],
        "rows": [["张三"]] * 20_000,
        "row_count": 20_000,
    }

    result = bound_audit_payload(source, max_bytes=1024)

    encoded = json.dumps(result, ensure_ascii=True).encode("utf-8")

    assert len(encoded) <= 1024
    assert result["__audit_trace"]["truncated"] is True
