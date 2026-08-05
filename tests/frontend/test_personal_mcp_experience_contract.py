"""Contract tests: personal center exposes My MCP (personalOnly), aligned with My Skills."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PERSONAL_CENTER = ROOT / "frontend" / "src" / "views" / "PersonalCenter.vue"
MCP_MGMT = ROOT / "frontend" / "src" / "views" / "McpManagement.vue"
MCP_REGISTRY = ROOT / "frontend" / "src" / "components" / "system" / "McpServerRegistry.vue"
MCP_CASCADE = ROOT / "frontend" / "src" / "components" / "embed" / "McpCascadeMenu.vue"


def test_personal_center_exposes_mcp_tab():
    text = PERSONAL_CENTER.read_text(encoding="utf-8")
    assert "'mcp'" in text or '"mcp"' in text
    assert "我的 MCP" in text
    assert "McpManagement" in text
    assert "personal-only" in text or "personalOnly" in text


def test_mcp_management_supports_personal_only_mode():
    text = MCP_MGMT.read_text(encoding="utf-8")
    assert "personalOnly" in text
    assert "v-if=\"!personalOnly\"" in text
    assert "我的 MCP" in text
    # 个人中心嵌入时不锁死 overflow，避免移动端裁切
    assert "personalOnly ? 'min-h-0'" in text or "personalOnly ? 'min-h-[28rem]'" in text


def test_mcp_cascade_empty_state_points_to_personal_center():
    text = MCP_CASCADE.read_text(encoding="utf-8")
    assert "/dashboard/personal?tab=mcp" in text
    assert "个人中心 · 我的 MCP" in text


def test_mcp_registry_mobile_master_detail_and_touch_actions():
    """窄屏改为列表/详情切换，触屏常显测试/发布按钮。"""
    text = MCP_REGISTRY.read_text(encoding="utf-8")
    assert "lg:flex-row" in text
    assert "clearSelectedServer" in text
    assert "ChevronLeftIcon" in text
    assert "返回服务列表" in text
    assert "hidden lg:flex" in text
    assert "opacity-100 lg:opacity-0 lg:group-hover:opacity-100" in text
    assert "max-h-[92dvh]" in text or "92dvh" in text
