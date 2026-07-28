from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure

ROOT = Path(__file__).resolve().parents[2]
SYSTEM_CONFIG = ROOT / "frontend/src/views/SystemConfig.vue"
MCP_MANAGEMENT = ROOT / "frontend/src/views/McpManagement.vue"
ROUTER = ROOT / "frontend/src/router/index.ts"


def test_system_config_does_not_render_legacy_mcp_tab():
    source = SYSTEM_CONFIG.read_text()

    assert "@click=\"activeTab = 'mcp'\"" not in source
    assert "MCP管理" not in source


def test_mcp_management_remains_a_standalone_dashboard_page():
    management_source = MCP_MANAGEMENT.read_text()
    router_source = ROUTER.read_text()

    assert "McpServerRegistry" in management_source
    assert "path: 'mcp'" in router_source
    assert "name: 'McpManagement'" in router_source
