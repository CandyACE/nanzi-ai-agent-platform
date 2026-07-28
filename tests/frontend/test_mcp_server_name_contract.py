from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "frontend/src/components/system/McpServerRegistry.vue"
NAME_HELPER = ROOT / "frontend/src/utils/mcpServerName.ts"


def test_mcp_default_name_uses_scope_prefix_and_actual_host_name():
    registry_source = REGISTRY.read_text()
    helper_source = NAME_HELPER.read_text()

    assert "buildDefaultMcpServerName" in registry_source
    assert "mcp-public-" in helper_source
    assert "mcp-private-" in helper_source
    assert "userInfo.value?.user_name" in registry_source
    assert "url.hostname" in registry_source


def test_mcp_default_name_is_only_applied_when_name_is_empty():
    registry_source = REGISTRY.read_text()

    assert "if (!newServer.value.server_name)" in registry_source
    assert "newServer.value.server_name = buildDefaultMcpServerName" in registry_source
