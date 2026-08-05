"""前端契约：MCP 服务备注字段。"""

from pathlib import Path

import pytest

pytestmark = pytest.mark.no_infrastructure

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = (ROOT / "frontend/src/components/system/McpServerRegistry.vue").read_text(encoding="utf-8")
MCP_MENU = (ROOT / "frontend/src/components/embed/McpCascadeMenu.vue").read_text(encoding="utf-8")
RESOURCE_MODAL = (ROOT / "frontend/src/components/embed/ResourceScopeModal.vue").read_text(encoding="utf-8")
MCP_API = (ROOT / "app/api/portal/endpoints/mcp.py").read_text(encoding="utf-8")
TOOLS_API = (ROOT / "app/api/portal/endpoints/tools.py").read_text(encoding="utf-8")
MODEL = (ROOT / "app/models/mcp.py").read_text(encoding="utf-8")
MYSQL_MIG = ROOT / "db-prod/V114-add_mcp_server_remark.sql"
PG_MIG = ROOT / "db-prod-pg/V13-add_mcp_server_remark.sql"


def test_mcp_server_remark_migrations_exist():
    assert MYSQL_MIG.exists()
    assert PG_MIG.exists()
    assert "remark" in MYSQL_MIG.read_text(encoding="utf-8")
    assert "remark" in PG_MIG.read_text(encoding="utf-8")


def test_mcp_server_model_and_api_support_remark():
    assert "remark = Column(String(500)" in MODEL
    assert "remark: Optional[str]" in MCP_API
    assert "_normalized_remark" in MCP_API
    assert 'if "remark" in data.model_fields_set' in MCP_API
    assert '"server_remark"' in TOOLS_API


def test_mcp_registry_wizard_has_optional_remark_field():
    assert "备注" in REGISTRY
    assert "newServer.remark" in REGISTRY
    assert "remark: server.remark || ''" in REGISTRY or "remark: server.remark" in REGISTRY
    assert "maxlength=\"500\"" in REGISTRY


def test_mcp_cascade_and_resource_modal_show_server_remark():
    assert "server_remark" in MCP_MENU
    assert "serverRemark" in MCP_MENU
    assert "server_remark" in RESOURCE_MODAL
    assert "serverRemark" in RESOURCE_MODAL


def test_agent_version_editor_shows_mcp_server_remark():
    drawer = (ROOT / "frontend/src/components/agent/AgentVersionEditorDrawer.vue").read_text(
        encoding="utf-8"
    )
    management = (ROOT / "frontend/src/views/AgentManagement.vue").read_text(encoding="utf-8")
    assert "server_remark" in drawer
    assert "tools[0].server_remark" in drawer or "tools[0]?.server_remark" in drawer
    assert "server_remark" in management
