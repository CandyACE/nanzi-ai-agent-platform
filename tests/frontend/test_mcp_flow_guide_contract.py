from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.no_infrastructure


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_mcp_flow_guide_banner_contract():
    banner = _source("frontend/src/components/mcp/McpFlowGuideBanner.vue")
    view = _source("frontend/src/views/McpManagement.vue")

    # 1. 验证 5 步流程定义与核心业务规则
    assert "服务登记与生态安装" in banner
    assert "探活发现与工具同步" in banner
    assert "在线测试与参数调试" in banner
    assert "范围隔离与权限分配" in banner
    assert "智能体挂载与协同调用" in banner

    # 2. 验证关键动作与路由跳转
    assert "/dashboard/roles" in banner
    assert "/dashboard/agent-management" in banner
    assert "新增服务" in banner
    assert "生态市场" in banner
    assert "不再提示" in banner

    # 3. 验证主视图中的组件引入与持久化机制
    assert "McpFlowGuideBanner" in view
    assert "nanzi_mcp_flow_guide_dismissed" in view
    assert "showMcpFlowGuide" in view
    assert "restoreMcpFlowGuide" in view
    assert "显示流程指引" in view

    # 4. 验证 ? 号规范弹窗中的全流程指引与恢复按钮
    assert "showHelp" in view
    assert "activeHelpTab" in view
    assert "MCP 工具集设计规范与全流程指引" in view
    assert "恢复顶部流程提示" in view
