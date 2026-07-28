from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure

SOURCE = Path(
    "frontend/src/components/system/McpServerRegistry.vue"
).read_text()


def test_mcp_registry_loads_and_displays_server_usage_summary():
    assert "fetchServerUsage" in SOURCE
    assert "/api/portal/mcp/servers/${serverId}/usage" in SOURCE
    assert "selectedServerUsage" in SOURCE
    assert "bound_agent_count" in SOURCE
    assert "active_agent_count" in SOURCE


def test_mcp_registry_checks_usage_before_disable_and_delete():
    assert "handleServerStatusChange" in SOURCE
    assert "showStatusConfirm" in SOURCE
    assert "deleteServerUsage" in SOURCE
    assert "受影响智能体" in SOURCE
    assert ":loading=\"deleteLoading\"" in SOURCE
