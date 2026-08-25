from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.no_infrastructure


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_skill_flow_guide_banner_contract():
    banner = _source("frontend/src/components/skill/SkillFlowGuideBanner.vue")
    view = _source("frontend/src/views/SkillsManagement.vue")

    # 1. 验证 5 步流程定义与核心业务规则
    assert "技能创建与目录规划" in banner
    assert "脚本编写与沙箱调试" in banner
    assert "提审申请与平台合规" in banner
    assert "平台发布与版本隔离" in banner
    assert "智能体绑定与动态激活" in banner

    # 2. 验证关键动作与路由跳转
    assert "新建技能" in banner
    assert "前往待审核" in banner
    assert "平台技能" in banner
    assert "/dashboard/agent-management" in banner
    assert "不再提示" in banner

    # 3. 验证主视图中的组件引入与持久化机制
    assert "SkillFlowGuideBanner" in view
    assert "nanzi_skill_flow_guide_dismissed" in view
    assert "showSkillFlowGuide" in view
    assert "restoreSkillFlowGuide" in view
    assert "显示流程指引" in view

    # 4. 验证 ? 号规范弹窗中的全流程指引与恢复按钮
    assert "showHelpModal" in view
    assert "activeHelpTab" in view
    assert "技能工作台研发规范与全流程指引" in view
    assert "恢复顶部流程提示" in view
