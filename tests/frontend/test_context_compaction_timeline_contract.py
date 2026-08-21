from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.no_infrastructure


def test_shared_context_compaction_timeline_covers_all_record_states_and_metrics():
    component = (ROOT / "frontend/src/components/chat/ContextCompactionTimeline.vue").read_text(
        encoding="utf-8",
    )
    chat_logs = (ROOT / "frontend/src/views/ChatLogs.vue").read_text(encoding="utf-8")

    assert "context-compaction-details" not in component
    assert "context_summarized" in component
    assert "context_compression" in component
    assert "record.source" in component
    assert "record.stage" in component
    assert "record.occurred_at" in component
    assert "record.dropped" in component
    assert "record.kept" in component
    assert "record.token_used" in component
    assert "record.summary_chars" in component
    assert "record.preview" in component
    assert "loading" in component
    assert "error" in component
    assert "重试" in component
    assert "emit('refresh')" in component or 'emit("refresh")' in component
    assert "v-html" not in component
    assert "ContextCompactionTimeline" in chat_logs
    assert "activeDetailTab === 'context'" in chat_logs
