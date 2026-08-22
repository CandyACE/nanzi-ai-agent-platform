from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.no_infrastructure


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_context_bar_uses_request_input_scale_and_separates_history_compaction_budget():
    modal = _read("frontend/src/components/chat/ChatModelCallStatsModal.vue")

    assert "const requestInputBudgetPct" in modal
    assert "stat.request_input_budget" in modal
    assert "contextUsageBarClass" in modal
    assert "requestInputBudgetPct(stat)" in modal
    assert "请求输入线" in modal
    assert "历史 compact 预算" in modal
    assert "const contextBudgetPct" not in modal


def test_model_call_stats_modal_shows_context_breakdown_categories():
    modal = _read("frontend/src/components/chat/ChatModelCallStatsModal.vue")

    assert "context_breakdown" in modal
    assert "system_prompt_tokens" in modal
    assert "tools_tokens" in modal
    assert "conversation_tokens" in modal
    assert "系统提示词" in modal
    assert "工具 schema" in modal
    assert "对话消息" in modal
    assert "估算" in modal
