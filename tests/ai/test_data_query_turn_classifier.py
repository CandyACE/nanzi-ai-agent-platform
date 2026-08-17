from unittest.mock import AsyncMock, patch

import pytest

from app.services.ai.data_query_turn_classifier import (
    DataQueryTurnType,
    _classify_with_llm,
    looks_like_chart_format_correction,
    resolve_data_query_turn_classification,
)


pytestmark = pytest.mark.no_infrastructure


@pytest.mark.asyncio
async def test_classifier_prompt_includes_federated_turn_type():
    captured = {}

    class FakeChatClient:
        async def generate_structured_dict(self, messages, structured_model):
            return None

        async def generate_text(self, messages):
            captured["messages"] = messages
            return '{"turn_type":"federated_data_query","reasoning":"跨数据集查询"}'

    with patch(
        "app.services.ai.config.AgentConfigProvider.get_configured_llm",
        AsyncMock(return_value=object()),
    ), patch(
        "app.services.ai.data_query_turn_classifier.chat_client_from_handle",
        return_value=FakeChatClient(),
    ):
        classification = await _classify_with_llm(
            "跨数据集关联 CRM 和员工数据",
            [{"role": "user", "content": "跨数据集关联 CRM 和员工数据"}],
            has_last_data_result=False,
        )

    prompt_text = "\n".join(str(getattr(msg, "content", msg)) for msg in captured["messages"])
    assert "federated_data_query" in prompt_text
    assert classification.turn_type == DataQueryTurnType.FEDERATED_DATA_QUERY


def test_chart_format_correction_does_not_capture_fresh_query_requests():
    assert looks_like_chart_format_correction("把刚才的图改成柱状图") is True
    assert looks_like_chart_format_correction("显示数值标签") is True
    assert looks_like_chart_format_correction("按地区把颜色改为分组再查一遍") is False
    assert looks_like_chart_format_correction("重新查询本月数据并显示数值") is False


@pytest.mark.asyncio
async def test_result_analysis_reuses_previous_result_without_intent_llm():
    with patch(
        "app.services.ai.config.AgentConfigProvider.get_configured_llm",
        AsyncMock(side_effect=AssertionError("result follow-up must short-circuit")),
    ):
        classification, _, elapsed_ms = await resolve_data_query_turn_classification(
            "可视化分析一下",
            [
                {"role": "user", "content": "查询算力SU回款"},
                {"role": "assistant", "content": "| 月份 | 回款率 |\n| --- | --- |"},
                {"role": "user", "content": "可视化分析一下"},
            ],
            has_last_data_result=True,
        )

    assert classification.turn_type == DataQueryTurnType.RESULT_ANALYSIS
    assert classification.requires_fresh_data is False
    assert classification.skip_intent_llm is True
    assert elapsed_ms == 0.0
