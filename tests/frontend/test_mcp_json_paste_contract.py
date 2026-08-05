"""契约与解析：MCP 登记支持粘贴 mcpServers JSON。"""

from pathlib import Path

import pytest

pytestmark = pytest.mark.no_infrastructure

ROOT = Path(__file__).resolve().parents[2]
PARSER = (ROOT / "frontend/src/utils/parseMcpServersPaste.ts").read_text(encoding="utf-8")
REGISTRY = (ROOT / "frontend/src/components/system/McpServerRegistry.vue").read_text(encoding="utf-8")


def test_parse_mcp_servers_paste_util_exists():
    assert "parseMcpServersPaste" in PARSER
    assert "suggestMcpNameSuffixFromKey" in PARSER
    assert "mcpServers" in PARSER
    assert "serverUrl" in PARSER
    assert "streamable_http" in PARSER


def test_mcp_registry_has_json_paste_flow():
    assert "parseMcpServersPaste" in REGISTRY
    assert "applyMcpJsonPaste" in REGISTRY
    assert "connectionInputTab" in REGISTRY
    assert "JSON 粘贴" in REGISTRY
    assert "解析并连接发现工具" in REGISTRY
    assert "applyMcpJsonPaste({ connect: true })" in REGISTRY
    assert "mcpJsonPaste" in REGISTRY
