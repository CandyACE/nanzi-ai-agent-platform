from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure

SOURCE = Path(
    "frontend/src/components/system/McpServerRegistry.vue"
).read_text()


def test_mcp_server_card_exposes_enabled_status_switch():
    assert "import Switch from '../Switch.vue'" in SOURCE
    assert "toggleServerStatus" in SOURCE
    assert "server.enabled_status === 1" in SOURCE
    assert "已禁用" in SOURCE


def test_mcp_server_status_switch_updates_existing_server_configuration():
    assert "@update:model-value=\"handleServerStatusChange(server, $event)\"" in SOURCE
    assert "const handleServerStatusChange = async" in SOURCE
    assert "`/api/portal/mcp/servers/${server.id}`" in SOURCE
    assert "enabled_status: nextStatus" in SOURCE
