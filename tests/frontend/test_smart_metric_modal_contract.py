"""Frontend contract test for SmartMetricModal.vue."""

from pathlib import Path
import pytest

pytestmark = pytest.mark.no_infrastructure


def test_smart_metric_modal_contract():
    modal_path = Path("frontend/src/components/metadata/SmartMetricModal.vue")
    assert modal_path.exists(), "SmartMetricModal.vue must exist"

    content = modal_path.read_text(encoding="utf-8")

    # 1. 验证表筛选与折叠相关契约
    assert "selectedTableNames" in content
    assert "isTablesCollapsed" in content
    assert "toggleTable" in content
    assert "toggleSelectAllTables" in content
    assert "tableSearchQuery" in content
    assert "分析数据表范围" in content

    # 2. 验证自定义需求与偏好提示词契约
    assert "userPrompt" in content
    assert "自定义业务偏好与关注点" in content
    assert "promptExamples" in content

    # 3. 验证问号帮助弹层与示例一键应用契约
    assert "showHelpModal" in content
    assert "applyPromptExample" in content
    assert "业务偏好提示词：填写指南与影响说明" in content
    assert "具体会带来哪些影响" in content
    assert "四段式填法结构" in content

    # 4. 验证 10 分钟去重防重提示与请求传参契约
    assert "10 分钟内自动去重" in content or "10分钟" in content
    assert "table_names" in content
    assert "user_prompt" in content

    # 5. 验证计时数秒、取消生成与耐心等待提示契约
    assert "elapsedSeconds" in content
    assert "handleCancelRecommend" in content
    assert "取消生成" in content
    assert "AI 努力生成中" in content or "可能较为耗时" in content
    assert "耐心等待" in content

    # 6. 推荐指标单项详情弹窗契约
    assert "selectedRecommendationIndex" in content
    assert "openRecommendationDetail" in content
    assert "closeRecommendationDetail" in content
    assert "查看详情" in content
    assert '@click.stop="openRecommendationDetail(idx)"' in content
    assert "item.calculation_logic" in content
    assert "item.description" in content
    assert "selectedRecommendation.tags" in content
