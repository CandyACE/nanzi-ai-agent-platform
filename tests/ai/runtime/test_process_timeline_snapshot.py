import pytest

from app.services.ai.runtime.agentscope.process_timeline_snapshot import (
    apply_stream_chunk,
    finalize_process_timeline,
)


pytestmark = pytest.mark.no_infrastructure


def _run(chunks):
    state = []
    for chunk in chunks:
        apply_stream_chunk(state, chunk)
    return finalize_process_timeline(state)


def test_committed_narration_and_tool_are_kept_promoted_candidate_is_dropped():
    items = _run(
        [
            {"type": "process_narration", "content": "我先搜一下。"},
            {"type": "process_narration_commit", "content": "我先搜一下。"},
            {
                "type": "log",
                "id": "tool_1",
                "title": "调用工具: search",
                "details": "query=晋景",
                "status": "success",
                "category": "tool",
                "execution_time_ms": 120,
            },
            {"type": "process_narration", "content": "# 最终报告\n正文"},
            {"type": "process_narration_promote", "content": "# 最终报告\n正文"},
        ]
    )

    kinds = [(item.get("kind"), item.get("textKind"), item.get("pending")) for item in items]
    assert ("text", "narration", False) in kinds
    assert not any(item.get("pending") for item in items)
    narration = next(item for item in items if item.get("textKind") == "narration")
    assert narration["content"] == "我先搜一下。"
    assert narration["children"][0]["title"] == "调用工具: search"
    assert "# 最终报告" not in str(items)


def test_router_log_becomes_intent_style_step_without_raw_event_fields():
    items = _run(
        [
            {
                "type": "router_log",
                "thought": "用户在问数据",
                "selected_agent": "chatbi",
                "confidence": 0.9,
                "status": "success",
                "execution_time_ms": 40,
            }
        ]
    )

    assert len(items) == 1
    assert items[0]["kind"] == "log"
    assert items[0]["title"] == "智能路由决策"
    assert items[0]["category"] == "router"
    assert "用户在问数据" in items[0]["details"]
    assert "chatbi" in items[0]["details"]
    assert "thought" not in items[0]


def test_tool_details_are_truncated_and_empty_snapshot_is_omitted():
    huge = "抓取结果" * 800
    items = _run(
        [
            {
                "type": "log",
                "id": "tool_big",
                "title": "调用工具: crawl",
                "details": huge,
                "status": "success",
                "category": "tool",
            }
        ]
    )
    assert len(items[0]["details"]) < len(huge)
    assert items[0]["details"].endswith("…")
    assert finalize_process_timeline([]) is None
    assert finalize_process_timeline([{"kind": "text", "textKind": "narration", "pending": True, "content": "候选"}]) is None


def test_model_call_start_and_end_merge_into_one_timeline_step():
    items = _run(
        [
            {
                "type": "model_call",
                "phase": "start",
                "reply_id": "r1",
                "model_name": "deepseek-chat",
            },
            {"type": "process_narration", "content": "我先搜一下。"},
            {"type": "process_narration_commit", "content": "我先搜一下。"},
            {
                "type": "log",
                "id": "tool_1",
                "title": "调用工具: search",
                "status": "success",
                "category": "tool",
            },
            {
                "type": "model_call",
                "phase": "end",
                "reply_id": "r1",
                "input_tokens": 100,
                "output_tokens": 20,
                "duration_ms": 1500,
            },
            {
                "type": "model_call",
                "phase": "start",
                "reply_id": "r2",
                "model_name": "deepseek-chat",
            },
            {
                "type": "model_call",
                "phase": "end",
                "reply_id": "r2",
                "input_tokens": 80,
                "output_tokens": 40,
                "duration_ms": 900,
            },
        ]
    )

    models = [item for item in items if item.get("category") == "model"]
    assert len(models) == 2
    assert models[0]["title"] == "模型调用: deepseek-chat"
    assert models[0]["status"] == "success"
    assert models[0]["details"] == "输入 100 / 输出 20 tokens，耗时 1500 ms"
    assert models[0]["execution_time_ms"] == 1500
    assert models[1]["details"] == "输入 80 / 输出 40 tokens，耗时 900 ms"
    assert items[0]["category"] == "model"
    assert items[1]["textKind"] == "narration"


def test_history_persistence_contract_covers_redis_audit_and_api():
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    mysql = (root / "db-prod/V121-add_process_timeline_to_history.sql").read_text(encoding="utf-8")
    pg = (root / "db-prod-pg/V21-add_process_timeline_to_history.sql").read_text(encoding="utf-8")
    model = (root / "app/models/audit.py").read_text(encoding="utf-8")
    schema = (root / "app/schemas/agent.py").read_text(encoding="utf-8")
    audit = (root / "app/services/ai/audit.py").read_text(encoding="utf-8")
    chat = (root / "app/api/v1/endpoints/chat.py").read_text(encoding="utf-8")
    memory = (root / "app/services/ai/memory_service.py").read_text(encoding="utf-8")

    assert "process_timeline" in mysql
    assert "process_timeline" in pg
    assert "process_timeline" in model
    assert "process_timeline" in schema
    assert "process_timeline" in audit
    assert '"process_timeline"' in chat or "process_timeline" in chat
    assert "process_timeline" in memory
