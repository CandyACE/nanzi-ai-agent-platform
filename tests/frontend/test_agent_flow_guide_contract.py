from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.no_infrastructure


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_agent_flow_guide_banner_contract():
    banner = _source("frontend/src/components/agent/AgentFlowGuideBanner.vue")
    view = _source("frontend/src/views/AgentManagement.vue")

    # 1. 验证 5 步流程定义与核心业务规则
    assert "定义与系统标识" in banner
    assert "系统智能体" in banner
    assert "模型与能力装配" in banner
    assert "版本管理与发布" in banner
    assert "角色授权与权限" in banner
    assert "调试与渠道消费" in banner

    # 2. 验证关键动作与路由跳转
    assert "/dashboard/roles" in banner
    assert "/dashboard/agent-debug" in banner
    assert "/dashboard/scenario-templates" in banner
    assert "/dashboard/skills" in banner
    assert "新建智能体" in banner
    assert "不再提示" in banner

    # 3. 验证主视图中的组件引入与持久化机制
    assert "AgentFlowGuideBanner" in view
    assert "nanzi_agent_flow_guide_dismissed" in view
    assert "showAgentFlowGuide" in view
    assert "restoreAgentFlowGuide" in view
    assert "显示流程指引" in view

    # 4. 验证 ? 号规范弹窗中的全流程指引与恢复按钮
    assert "showHelp" in view
    assert "activeHelpTab" in view
    assert "智能体设计规范与全流程指引" in view
    assert "恢复顶部流程提示" in view
