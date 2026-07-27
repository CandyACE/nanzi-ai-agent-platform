from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.no_infrastructure


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_chart_card_supports_table_view():
    source = _source("frontend/src/components/MessageRenderer.vue")

    assert "buildChartTableRows" in source
    assert "localChartTypes[idx] = 'table'" in source
    assert "title=\"切换为表格视图\"" in source
    assert "表格" in source
    assert "v-if=\"localChartTypes[idx] === 'table'\"" in source


def test_message_renderer_supports_clarification_card():
    source = _source("frontend/src/components/MessageRenderer.vue")

    assert ":::clarification" in source
    assert "'clarification'" in source
    assert "clarification-card" in source
    assert "需要你确认" in source
    assert "clarification-card__icon" in source


def test_message_renderer_wraps_markdown_tables_with_scroll_container():
    source = _source("frontend/src/components/MessageRenderer.vue")

    assert "markdown-table-scroll" in source
    assert "<div class=\"markdown-table-scroll\">${table}</div>" in source


def test_embed_markdown_tables_have_breathing_room_and_mobile_overflow():
    source = _source("frontend/src/views/EmbedChat.vue")

    assert ":deep(.markdown-body .markdown-table-scroll)" in source
    assert ":deep(.markdown-body table)" in source
    for token in (
        "min-width: 680px",
        "overflow-x: auto",
        "border-spacing: 0",
        "display: table",
        "padding: 10px 14px",
        "vertical-align: top",
        "overflow-wrap: anywhere",
    ):
        assert token in source

    assert "display: block;\n  width: 100%;\n  min-width: 680px" not in source
