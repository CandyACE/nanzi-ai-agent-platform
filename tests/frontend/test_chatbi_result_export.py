"""Tests for ChatBI result Markdown export helpers."""

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.no_infrastructure


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_chatbi_result_markdown_export_contract():
    util = _source("frontend/src/utils/chatbiResultExport.ts")
    panel = _source("frontend/src/components/chatbi/ChatBIInsightPanel.vue")

    assert "export function buildChatBIResultMarkdown" in util
    assert "export function exportChatBIResultMarkdown" in util
    assert "downloadMarkdownFile" in util
    assert "ChatBI 查询结果明细" in util
    assert "导出 Markdown" in panel
    assert "exportChatBIResultMarkdown" in panel
    assert "exportMarkdown" in panel
