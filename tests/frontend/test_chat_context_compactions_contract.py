from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure

ROOT = Path(__file__).resolve().parents[2]


def test_chat_logs_exposes_context_tab_and_lazy_context_timeline():
    source = (ROOT / "frontend/src/views/ChatLogs.vue").read_text()
    timeline_source = (ROOT / "frontend/src/components/chat/ContextCompactionTimeline.vue").read_text()
    api_source = (ROOT / "frontend/src/api/agent.ts").read_text()

    assert "上下文" in source
    assert "activeDetailTab === 'context'" in source
    assert "loadContextCompactions" in source
    assert "contextRequestVersion" in source
    assert "requestVersion !== contextRequestVersion" in source
    assert "ContextCompactionTimeline" in source
    assert "context_compactions" in api_source
    assert "summary_chars" in timeline_source
    assert "preview" in timeline_source
    assert "dropped" in timeline_source
    assert "kept" in timeline_source
