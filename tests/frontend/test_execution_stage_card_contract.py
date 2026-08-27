"""执行链路卡片的六阶段展示契约。"""

from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure

ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_execution_stage_model_exposes_six_user_facing_stages():
    source = _read("frontend/src/utils/executionStages.ts")

    expected_stages = [
        ("request", "请求校验", "鉴权、参数校验、会话资源与幂等校验"),
        ("context", "会话上下文", "读取普通历史并控制上下文窗口"),
        ("entry", "入口确认", "确认默认 Main 或指定专家，并校验权限"),
        ("capability", "能力准备", "加载模型、知识库、Skill、专家清单并组装 Prompt"),
        ("execution", "智能执行", "Main 直接回答，或调用工具、自动委派其他智能体"),
        ("output", "输出完成", "流式输出、保存结果并记录审计信息"),
    ]

    for stage_id, title, summary in expected_stages:
        assert f'"{stage_id}"' in source
        assert f'title: "{title}"' in source
        assert summary in source
    assert "items: ProcessTimelineItem[]" in source
    assert '"upcoming"' in source


def test_execution_timeline_renders_stage_groups_and_keeps_raw_items_expandable():
    source = _read("frontend/src/components/chat/ChatExecutionTimeline.vue")

    assert "buildExecutionStages" in source
    assert "executionStages" in source
    assert 'v-for="stage in executionStages"' in source
    assert "stage.items" in source
    assert "isStageExpanded(stage.id)" in source
    assert "切换阶段展开状态" in source
    assert "原始执行明细" in source
    assert ":step-count=\"executionStages.length\"" in source
    assert ":detail-count=\"countTimelineSteps(items)\"" in source


def test_thinking_header_can_distinguish_stage_count_from_detail_count():
    source = _read("frontend/src/components/chat/ChatThinkingHeader.vue")

    assert "detailCount" in source
    assert "个明细" in source
