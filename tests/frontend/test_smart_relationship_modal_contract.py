"""Frontend contract test for SmartRelationshipModal.vue and RelationshipList.vue."""

from pathlib import Path
import pytest

pytestmark = pytest.mark.no_infrastructure


def test_smart_relationship_modal_contract():
    modal_path = Path("frontend/src/components/metadata/SmartRelationshipModal.vue")
    assert modal_path.exists(), "SmartRelationshipModal.vue must exist"

    content = modal_path.read_text(encoding="utf-8")

    # 1. 验证表筛选与折叠相关契约
    assert "selectedTableNames" in content
    assert "isTablesCollapsed" in content
    assert "toggleTable" in content
    assert "toggleSelectAllTables" in content
    assert "tableSearchQuery" in content
    assert "需至少选择 2 张表" in content or "至少选择 2 张" in content

    # 2. 验证自定义需求与偏好提示词契约
    assert "userPrompt" in content
    assert "promptExamples" in content
    assert "通用关联模式" in content

    # 3. 验证问号帮助弹层与示例一键应用契约
    assert "showHelpModal" in content
    assert "applyPromptExample" in content
    assert "实体关系智能推导：指南与说明" in content
    assert "具体会带来哪些影响" in content

    # 4. 验证计时数秒、取消生成与去重提示
    assert "elapsedSeconds" in content
    assert "handleCancelRecommend" in content
    assert "取消生成" in content
    assert "bg-red-50" in content
    assert "text-red-600" in content
    assert "border-red-200" in content
    assert "bg-white hover:bg-red-50 text-gray-600 hover:text-red-600 border border-gray-300 hover:border-red-200" not in content
    assert "10 分钟内自动去重" in content or "自动排除已有实体关系" in content

    # 5. 验证 RelationshipList.vue 绑定了 SmartRelationshipModal
    list_path = Path("frontend/src/components/metadata/RelationshipList.vue")
    assert list_path.exists(), "RelationshipList.vue must exist"
    list_content = list_path.read_text(encoding="utf-8")
    assert "SmartRelationshipModal" in list_content
    assert "showSmartRelModal" in list_content

    # 关系推荐可能逐表执行较长时间，不能被固定的 5 分钟客户端超时误判为失败。
    api_path = Path("frontend/src/api/metadata.ts")
    api_content = api_path.read_text(encoding="utf-8")
    assert "relationships/recommend" in api_content
    assert "{ timeout: 0, signal }" in api_content
    assert "关系推荐请求失败" in content
