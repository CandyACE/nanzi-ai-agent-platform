"""执行卡片前置生命周期明细契约。"""

from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure

ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_chat_timeline_keeps_original_step_counter_and_does_not_add_stage_wrapper():
    timeline = _read("frontend/src/components/chat/ChatExecutionTimeline.vue")
    header = _read("frontend/src/components/chat/ChatThinkingHeader.vue")

    assert ':step-count="countTimelineSteps(items)"' in timeline
    assert 'v-for="item in items"' in timeline
    assert "executionStages" not in timeline
    assert "detailCount" not in header


def test_backend_exposes_request_and_context_details_as_real_timeline_logs():
    source = _read("app/services/ai/agent_service.py")

    for helper in (
        "_build_request_validation_log",
        "_build_context_history_log",
        "_build_model_config_log",
        "_build_capability_catalog_log",
        "_build_prompt_assembly_log",
    ):
        assert helper in source

    assert '"请求校验"' in source
    assert '"会话上下文"' in source
    assert '"模型配置解析"' in source
    assert '"知识库和专家清单加载"' in source
    assert '"Prompt 组装"' in source
    assert "当前会话用户" in source
    assert "读取历史" in source
    assert "保留" in source
    assert "裁剪" in source


def test_preparation_parent_uses_auth_context_title_and_shield_icon():
    timeline = _read("frontend/src/components/chat/ChatExecutionTimeline.vue")
    assert "鉴权及上下文与能力准备" in timeline
    assert "parent_id" in timeline
    assert 'return "🛡️"' in timeline


def test_thinking_card_strengthens_parent_hierarchy_and_uses_user_facing_labels():
    timeline = _read("frontend/src/components/chat/ChatExecutionTimeline.vue")
    header = _read("frontend/src/components/chat/ChatThinkingHeader.vue")
    timeline_utils = _read("frontend/src/utils/processTimeline.ts")

    assert "isPreparationParent" in timeline
    assert "项准备" in timeline
    assert "bg-sky-50" not in timeline
    assert "border-sky-200" not in timeline
    assert "displayTimelineTitle" in timeline
    assert "collapseCompletedPreparation" in timeline
    assert "childrenExpanded = false" in timeline
    assert "watch(items" in timeline
    assert "主专家开始处理" in timeline_utils
    assert "工具可用性检查" in timeline_utils
    assert "模型调用 ·" in timeline_utils
    assert "#0ea5e9" in timeline
    assert "#0ea5e9" in header
