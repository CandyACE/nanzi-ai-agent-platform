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


def test_embed_ai_bubble_and_tables_follow_selected_markdown_theme():
    source = _source("frontend/src/views/EmbedChat.vue")

    assert "markdown-theme-${config.markdownTheme || 'default'}" in source
    for theme in ("default", "minimal", "academic", "apple", "warm", "compact", "bauhaus", "editorial", "zen"):
        assert f".markdown-theme-{theme}" in source
    assert ".markdown-theme-apple :deep(.markdown-table-scroll)" in source
    assert ".markdown-theme-editorial :deep(.markdown-table-scroll)" in source


def test_ai_message_border_visibility_is_configurable_and_persisted():
    management_source = _source("frontend/src/views/AgentManagement.vue")
    drawer_source = _source("frontend/src/components/agent/AgentVersionEditorDrawer.vue")
    embed_source = _source("frontend/src/views/EmbedChat.vue")

    assert "hide_message_border" in management_source
    assert "hide_message_border" in drawer_source
    assert "hideMessageBorder: false" in embed_source
    assert "message-borderless" in embed_source
    assert "config.hideMessageBorder" in embed_source


def test_embed_markdown_table_cells_are_left_aligned():
    source = _source("frontend/src/views/EmbedChat.vue")

    assert ":deep(.markdown-body th)" in source
    assert ":deep(.markdown-body td)" in source
    assert "text-align: left !important;" in source


def test_embed_settings_exposes_and_persists_message_border_preference():
    settings_source = _source("frontend/src/components/embed/ChatSettings.vue")
    embed_source = _source("frontend/src/views/EmbedChat.vue")

    assert "隐藏 AI 消息外框" in settings_source
    assert "handleSetMessageBorder" in settings_source
    assert "config.hideMessageBorder" in settings_source
    assert "yovole_hide_message_border" in embed_source
    assert "user_has_custom_border_preference" in embed_source


def test_bauhaus_message_background_is_white():
    source = _source("frontend/src/views/EmbedChat.vue")

    bauhaus_theme = source.split(".markdown-theme-bauhaus {", 1)[1].split("}", 1)[0]
    assert "--ai-bubble-background: #ffffff;" in bauhaus_theme
    assert "--md-table-background: #ffffff;" in bauhaus_theme
