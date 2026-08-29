from unittest.mock import AsyncMock, patch

import pytest

from app.services.ai.data_query_turn_classifier import (
    DataQueryTurnType,
    resolve_data_query_turn_classification,
)
from app.services.ai.reusable_result import (
    extract_reusable_action_query,
    prepare_reusable_route_input,
)


pytestmark = pytest.mark.no_infrastructure


def test_extract_reusable_action_query_ignores_clicked_reply_body():
    content = (
        "生成可视化分析报告\n\n---\n\n"
        "【被点击的 AI 回复】\n查询结果：共 10 条"
    )

    assert extract_reusable_action_query(content) == "生成可视化分析报告"


def test_extract_reusable_action_query_ignores_normalized_attachment_wrapper():
    content = (
        "查询本月销售额\n\n<system_injected_attachments>\n"
        "【被点击的 AI 回复】\n上一轮查询结果：统计了销售额\n"
        "</system_injected_attachments>"
    )

    assert extract_reusable_action_query(content) == "查询本月销售额"


def test_prepare_reusable_route_input_removes_clicked_reply_only_for_route():
    content = (
        "查询本月销售额\n\n---\n\n"
        "【被点击的 AI 回复】\n上一轮查询结果：统计了销售额"
    )
    messages = [
        {"role": "assistant", "content": "上一轮查询结果"},
        {"role": "user", "content": content},
    ]

    route_messages, route_query = prepare_reusable_route_input(messages, content)

    assert route_query == "查询本月销售额"
    assert route_messages[-1]["content"] == "查询本月销售额"
    assert messages[-1]["content"] == content


@pytest.mark.asyncio
async def test_clicked_reply_with_cached_result_is_classified_as_reuse_action():
    content = (
        "生成可视化分析报告\n\n---\n\n"
        "【被点击的 AI 回复】\n查询结果：共 10 条"
    )
    messages = [
        {"role": "assistant", "content": "查询结果：共 10 条"},
        {"role": "user", "content": content},
    ]

    with patch(
        "app.services.ai.data_query_turn_classifier._classify_with_llm",
        new_callable=AsyncMock,
        return_value=None,
    ):
        classification, _, _ = await resolve_data_query_turn_classification(
            content,
            messages,
            has_last_data_result=True,
        )

    assert classification.turn_type in {
        DataQueryTurnType.RESULT_ANALYSIS,
        DataQueryTurnType.RESULT_ACTION,
    }
    assert classification.requires_sql_query is False


@pytest.mark.asyncio
async def test_clicked_reply_without_cache_falls_back_to_new_query():
    content = (
        "生成可视化分析报告\n\n---\n\n"
        "【被点击的 AI 回复】\n查询结果：共 10 条"
    )

    with patch(
        "app.services.ai.data_query_turn_classifier._classify_with_llm",
        new_callable=AsyncMock,
        return_value=None,
    ):
        classification, _, _ = await resolve_data_query_turn_classification(
            content,
            [{"role": "user", "content": content}],
            has_last_data_result=False,
        )

    assert classification.turn_type == DataQueryTurnType.NEW_DATA_QUERY
    assert classification.requires_sql_query is True


@pytest.mark.asyncio
async def test_agent_service_resolves_current_and_stack_before_route():
    from app.services.ai.agent_service import AgentService

    current = {"result_id": "r-current", "result_type": "generic", "content": "结果"}
    with patch(
        "app.services.ai.agent_service.memory_service.get_reusable_result",
        new_callable=AsyncMock,
        return_value=current,
    ) as get_current, patch(
        "app.services.ai.agent_service.memory_service.get_reusable_result_stack",
        new_callable=AsyncMock,
        return_value=[current],
    ) as get_stack:
        decision = await AgentService()._resolve_reusable_result_decision(
            user_info={"user_id": 7},
            conversation_id="conv-1",
            user_query="基于刚才结果继续分析",
        )

    assert decision.mode == "reuse"
    assert decision.result["result_id"] == "r-current"
    get_current.assert_awaited_once_with("7", "conv-1")
    get_stack.assert_awaited_once_with("7", "conv-1")


@pytest.mark.asyncio
async def test_agent_service_can_apply_route_specific_result_type_filter():
    from app.services.ai.agent_service import AgentService

    current = {
        "result_id": "data-1",
        "result_type": "data",
        "status": "completed",
        "content": "数据结果",
    }
    with patch(
        "app.services.ai.agent_service.memory_service.get_reusable_result",
        new_callable=AsyncMock,
        return_value=current,
    ), patch(
        "app.services.ai.agent_service.memory_service.get_reusable_result_stack",
        new_callable=AsyncMock,
        return_value=[],
    ):
        decision = await AgentService()._resolve_reusable_result_decision(
            user_info={"user_id": 7},
            conversation_id="conv-1",
            user_query="继续分析上一轮结果",
            allowed_result_types={"knowledge"},
        )

    assert decision.mode == "fallback"
    assert decision.reason == "incompatible_result_type"


def test_resolve_reusable_result_prefers_valid_selected_stack_item():
    from app.services.ai.reusable_result import resolve_reusable_result

    selected = {
        "result_id": "rr_old",
        "result_type": "generic",
        "status": "success",
        "content": "old result",
    }
    current = {
        "result_id": "rr_new",
        "result_type": "generic",
        "status": "success",
        "content": "new result",
    }

    decision = resolve_reusable_result(
        "请继续分析",
        current=current,
        stack=[selected, current],
        preferred_result_id="rr_old",
    )

    assert decision.mode == "reuse"
    assert decision.result["result_id"] == "rr_old"


def test_resolve_reusable_result_ignores_invalid_selected_id():
    from app.services.ai.reusable_result import resolve_reusable_result

    decision = resolve_reusable_result(
        "查询本周订单",
        current=None,
        stack=[],
        preferred_result_id="rr_missing",
    )

    assert decision.mode == "fallback"
    assert decision.reason == "selected_result_missing"
