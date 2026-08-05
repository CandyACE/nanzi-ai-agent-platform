from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.no_infrastructure


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_canvas_markdown_preview_uses_rich_renderer_instead_of_raw_html_only():
    canvas = _source("frontend/src/components/embed/ChatCanvas.vue")

    assert "CanvasMarkdownRenderer" in canvas
    assert "<CanvasMarkdownRenderer" in canvas
    assert 'v-html="renderedMarkdownContent"' not in canvas


def test_canvas_markdown_renderer_supports_echarts_and_mermaid_fences():
    renderer = _source("frontend/src/components/embed/CanvasMarkdownRenderer.vue")

    assert "parseChartOptions" in renderer
    assert "mergeChartDefaults" in renderer
    assert "MermaidRenderer" in renderer
    assert "VChart" in renderer
    assert "chart|echarts|json" in renderer
    assert "mermaid" in renderer
    assert "CandlestickChart" in renderer


def test_canvas_markdown_renderer_keeps_invalid_json_as_markdown_code():
    renderer = _source("frontend/src/components/embed/CanvasMarkdownRenderer.vue")

    assert "parsed.ok" in renderer
    assert "appendMarkdown(rawBlock)" in renderer
