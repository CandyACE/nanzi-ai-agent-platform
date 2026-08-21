from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.no_infrastructure


def test_chat_input_exposes_compaction_count_and_timeline_modal_contract():
    source = (ROOT / "frontend/src/components/embed/ChatInput.vue").read_text(
        encoding="utf-8",
    )

    assert "contextCompactionCount" in source
    assert "contextCompactionRecords" in source
    assert "contextCompactionLoading" in source
    assert "contextCompactionError" in source
    assert "contextCompactionCount" in source
    assert "压缩" in source
    assert "contextIndicatorVisible" not in source
    assert "context-compaction-indicator" in source
    assert "context-compaction-details" in source
    assert "context-compaction-close" in source
    assert "showContextCompactionDetails" in source
    assert "ContextCompactionTimeline" in source
    assert "refresh-context-compactions" in source
    assert "contextCompactionDetailsPlacement" in source
    assert source.index('data-testid="context-usage-details"') < source.index('data-testid="context-compaction-indicator"')
