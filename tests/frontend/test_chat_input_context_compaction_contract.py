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


def test_chat_input_compaction_controls_use_two_row_responsive_layout():
    source = (ROOT / "frontend/src/components/embed/ChatInput.vue").read_text(
        encoding="utf-8",
    )

    compaction_start = source.index('v-if="contextCompactionEnabled"')
    compaction_end = source.index('v-if="sandboxPolicyLabel"', compaction_start)
    block = source[compaction_start:compaction_end]

    assert "grid" in block
    assert "上下文压缩" in block
    assert "压缩强度" in block
    assert "轻度 75%" in block
    assert "标准 50%" in block
    assert "深度 25%" in block
    assert "{{ contextCompactionCount }} 次记录" in block
    assert "立即压缩" in block
    assert "contextCompactionMode" in block
    assert "data-testid=\"context-compaction-mode-fast\"" in block
    assert "data-testid=\"context-compaction-mode-smart\"" in block


def test_chat_input_compaction_card_has_clear_hierarchy_and_primary_color():
    source = (ROOT / "frontend/src/components/embed/ChatInput.vue").read_text(
        encoding="utf-8",
    )

    compaction_start = source.index('v-if="contextCompactionEnabled"')
    compaction_end = source.index('v-if="sandboxPolicyLabel"', compaction_start)
    block = source[compaction_start:compaction_end]

    assert "压缩方式" in block
    assert "保留比例" in block
    assert 'data-testid="context-compaction-mode-fast"' in block
    assert 'data-testid="context-compaction-mode-smart"' in block
    assert "立即智能压缩" in block
    assert "智能压缩会调用模型" in block
    assert "bg-primary" in block
    assert "text-emerald" in block
    assert "violet" not in block


def test_chat_input_shows_latest_compaction_savings_and_clear_budget_labels():
    source = (ROOT / "frontend/src/components/embed/ChatInput.vue").read_text(
        encoding="utf-8",
    )

    assert "saved_tokens" in source
    assert "saved_percent" in source
    assert "本次节省" in source
    assert "自动压缩触发线" in source
    assert "请求输入上限" in source
