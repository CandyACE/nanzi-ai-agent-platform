import json
from datetime import datetime, timedelta, timezone

import pytest

from app.services.ai.reusable_result import (
    build_reusable_result,
    build_reusable_result_client_summary,
    build_reusable_result_status_event,
    is_reusable_result_candidate,
    normalize_legacy_data_result,
    normalize_legacy_reusable_result,
    resolve_reusable_result,
    sanitize_reusable_result_payload,
)


pytestmark = pytest.mark.no_infrastructure


def test_build_reusable_result_keeps_origin_and_safe_content():
    result = build_reusable_result(
        tool_name="sub_agent_call",
        tool_output={"answer": "方案正文"},
        source_type="system",
        tool_args={"token": "secret", "agent_name": "knowledge-agent"},
        user_question="请查手册",
        trace_id="trace-1",
        origin_type="sub_agent",
    )

    assert result["result_type"] == "knowledge"
    assert result["origin_type"] == "sub_agent"
    assert result["origin_name"] == "sub_agent_call"
    assert result["structured"] == {"answer": "方案正文"}
    assert result["tool_args"]["token"] == "[redacted]"

    result_with_token_variant = build_reusable_result(
        tool_name="system_http_request",
        tool_output="ok",
        source_type="system",
        tool_args={"access_token": "secret", "x-api-key": "secret"},
        user_question="请求接口",
        trace_id="trace-2",
    )
    assert result_with_token_variant["tool_args"] == {
        "access_token": "[redacted]",
        "x-api-key": "[redacted]",
    }

    result_with_datetime = build_reusable_result(
        tool_name="read_file",
        tool_output={"updated_at": datetime(2026, 8, 29, tzinfo=timezone.utc)},
        source_type="system",
        tool_args={},
        user_question="读取文件",
        trace_id="trace-3",
    )
    assert result_with_datetime["structured"] == {
        "updated_at": "2026-08-29 00:00:00+00:00"
    }


def test_build_reusable_result_redacts_sensitive_tool_output_before_persistence():
    result = build_reusable_result(
        tool_name="browser_read_visible",
        tool_output={
            "text": "Authorization: Bearer top-secret-token",
            "access_token": "nested-secret",
            "rows": [{"cookie": "session=private-cookie", "amount": 10}],
        },
        source_type="mcp",
        tool_args={},
        user_question="读取页面",
        trace_id="trace-sensitive-output",
    )

    serialized = json.dumps(result, ensure_ascii=False)
    assert "top-secret-token" not in serialized
    assert "nested-secret" not in serialized
    assert "private-cookie" not in serialized
    assert "[redacted]" in serialized


def test_sanitize_reusable_result_payload_cleans_unknown_extension_fields():
    payload = sanitize_reusable_result_payload({
        "result_id": "rr-unknown-fields",
        "result_type": "generic",
        "status": "completed",
        "output": {
            "privateKey": "private-key-value",
            "access_key": "access-key-value",
            "auth": "auth-value",
            "api key": "api-key-value",
            "token_count": 3,
            "message": "Authorization: Bearer text-secret",
        },
        "metadata": ["client_secret=metadata-secret", "eyJheader123.payload123.signature123"],
    })

    serialized = json.dumps(payload, ensure_ascii=False)
    assert "private-key-value" not in serialized
    assert "access-key-value" not in serialized
    assert "auth-value" not in serialized
    assert "api-key-value" not in serialized
    assert "text-secret" not in serialized
    assert "metadata-secret" not in serialized
    assert "eyJheader123.payload123.signature123" not in serialized
    assert payload["output"]["token_count"] == 3


def test_normalize_legacy_data_result_adds_canonical_fields():
    result = normalize_legacy_data_result({
        "sql": "SELECT 1",
        "dataset_name": "sales",
        "rows": {"rows": [{"region": "华东", "amount": 10}]},
        "saved_at": "2026-08-30T10:00:00+00:00",
    })

    assert result["result_type"] == "data"
    assert result["status"] == "completed"
    assert result["result_id"].startswith("legacy_data_")
    assert result["structured"] == result["rows"]
    assert result["content"]
    assert result["saved_at"] == "2026-08-30T10:00:00+00:00"


def test_normalize_legacy_reusable_result_infers_non_data_type():
    result = normalize_legacy_reusable_result({
        "tool_name": "browser_read_visible",
        "source_type": "mcp",
        "text_excerpt": "页面正文",
    })

    assert result["result_type"] == "web"
    assert result["origin_name"] == "browser_read_visible"
    assert result["result_id"].startswith("legacy_result_")


def test_reuse_decision_prefers_existing_result_but_allows_fallback_when_missing():
    hit = resolve_reusable_result(
        "请基于刚才结果生成报告",
        current={"result_id": "r1", "result_type": "generic", "content": "结果正文"},
        stack=[],
    )
    miss = resolve_reusable_result(
        "请基于刚才结果生成报告",
        current=None,
        stack=[],
    )

    assert hit.mode == "reuse"
    assert hit.result["result_id"] == "r1"
    assert miss.mode == "fallback"
    assert miss.reason == "missing_result"


def test_insufficient_existing_result_falls_back_instead_of_blocking_query():
    decision = resolve_reusable_result(
        "基于刚才结果生成可视化报告",
        current={"result_id": "r1", "result_type": "generic", "status": "empty"},
        stack=[],
    )

    assert decision.mode == "fallback"
    assert decision.reason == "insufficient_result"


def test_empty_structured_result_is_not_reusable():
    decision = resolve_reusable_result(
        "基于刚才结果生成可视化报告",
        current={
            "result_id": "r-empty",
            "result_type": "data",
            "status": "completed",
            "structured": {"rows": []},
        },
        stack=[],
    )

    assert decision.mode == "fallback"
    assert decision.reason == "insufficient_result"


def test_reusable_candidate_rejects_expired_fresh_or_disallowed_result():
    expired = {
        "result_id": "expired",
        "result_type": "generic",
        "status": "completed",
        "content": "旧结果",
        "expires_at": (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),
    }
    requires_fresh = {
        "result_id": "fresh",
        "result_type": "generic",
        "status": "completed",
        "content": "动态结果",
        "requires_fresh": True,
    }
    disallowed = {
        "result_id": "disallowed",
        "result_type": "generic",
        "status": "completed",
        "content": "禁止复用",
        "reuse_allowed": False,
    }

    assert is_reusable_result_candidate(expired) is False
    assert is_reusable_result_candidate(requires_fresh) is False
    assert is_reusable_result_candidate(disallowed) is False


def test_reusable_candidate_rejects_malformed_expiry():
    candidate = {
        "result_id": "malformed-expiry",
        "result_type": "generic",
        "status": "completed",
        "content": "结果",
        "expires_at": "not-a-timestamp",
    }

    assert is_reusable_result_candidate(candidate) is False


def test_selected_result_miss_does_not_fall_back_to_current_result():
    decision = resolve_reusable_result(
        "继续分析上一轮结果",
        current={
            "result_id": "current",
            "result_type": "generic",
            "status": "completed",
            "content": "当前结果",
        },
        stack=[],
        preferred_result_id="missing",
    )

    assert decision.mode == "fallback"
    assert decision.result is None
    assert decision.reason == "selected_result_missing"


def test_reusable_result_can_enforce_runner_result_type_compatibility():
    decision = resolve_reusable_result(
        "继续分析上一轮结果",
        current={
            "result_id": "data-1",
            "result_type": "data",
            "status": "completed",
            "content": "数据结果",
        },
        stack=[],
        allowed_result_types={"knowledge"},
    )

    assert decision.mode == "fallback"
    assert decision.reason == "incompatible_result_type"


def test_refresh_request_bypasses_existing_result():
    decision = resolve_reusable_result(
        "请重新查询最新数据",
        current={"result_id": "r1", "result_type": "data"},
        stack=[],
    )

    assert decision.mode == "fallback"
    assert decision.reason == "freshness_requested"


def test_clicked_reply_body_is_not_treated_as_freshness_request():
    decision = resolve_reusable_result(
        "生成可视化分析报告\n\n---\n\n【被点击的 AI 回复】\n这是最新数据的查询结果",
        current={"result_id": "r1", "result_type": "data", "content": "查询结果正文"},
        stack=[],
    )

    assert decision.mode == "reuse"


def test_unrelated_new_request_does_not_force_reuse():
    decision = resolve_reusable_result(
        "帮我写一个周报标题",
        current={"result_id": "r1", "result_type": "generic"},
        stack=[],
    )

    assert decision.mode == "none"


def test_build_reusable_result_client_summary_redacts_internal_fields():
    payload = {
        "result_id": "rr_1",
        "result_type": "data",
        "origin_name": "查数助手",
        "status": "success",
        "text_excerpt": "销售额结果",
        "structured": {"row_count": 20, "columns": ["区域", "销售额"]},
        "tool_args": {"dataset_name": "sales", "access_token": "secret-value"},
    }

    result = build_reusable_result_client_summary(payload, is_current=True)

    assert result["result_id"] == "rr_1"
    assert result["is_current"] is True
    assert result["structured_preview"]["row_count"] == 20
    assert "tool_args" not in result
    assert "access_token" not in json.dumps(result)


def test_build_reusable_result_client_summary_rejects_non_reusable_payload():
    assert build_reusable_result_client_summary({"status": "failed"}, is_current=False) is None
    assert build_reusable_result_client_summary({"result_id": "rr_empty"}, is_current=False) is None


def test_reusable_result_status_event_exposes_only_safe_metadata():
    event = build_reusable_result_status_event(
        status="saved",
        payload={
            "result_id": "rr_1",
            "result_type": "data",
            "origin_name": "查数助手",
            "status": "completed",
            "content": "销售额结果",
            "structured": {"rows": [{"amount": 10}]},
            "tool_args": {"access_token": "secret"},
            "saved_at": "2026-08-29T11:37:00Z",
        },
    )

    assert event["type"] == "reusable_result_status"
    assert event["status"] == "saved"
    assert event["result_id"] == "rr_1"
    assert event["result_type"] == "data"
    assert "content" not in event
    assert "structured" not in event
    assert "tool_args" not in event
