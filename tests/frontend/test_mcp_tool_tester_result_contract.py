from pathlib import Path

import pytest

pytestmark = pytest.mark.no_infrastructure

SOURCE = Path("frontend/src/components/system/McpToolTester.vue").read_text()


def test_mcp_tool_tester_pretty_prints_json_and_renders_markdown():
    assert "tryPrettyJson" in SOURCE
    assert "JSON.stringify" in SOURCE
    assert "looksLikeMarkdown" in SOURCE
    assert "renderSafeMarkdownPreview" in SOURCE
    assert "hljs.highlight" in SOURCE


def test_mcp_tool_tester_has_hover_copy_affordance():
    assert "copyToClipboard" in SOURCE
    assert "group/result" in SOURCE
    assert "handleCopyResult" in SOURCE
    assert "DocumentDuplicateIcon" in SOURCE
    assert "已复制到剪贴板" in SOURCE
