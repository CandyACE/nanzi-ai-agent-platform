from unittest.mock import AsyncMock, patch

import pytest

from app.services.ai.session_tool_artifact import (
    append_session_tool_artifact_to_system_prompt,
    load_session_tool_artifact,
)


pytestmark = pytest.mark.no_infrastructure


@pytest.mark.asyncio
async def test_assistant_artifact_loader_falls_back_to_unified_result():
    unified = {
        "result_id": "r1",
        "result_type": "knowledge",
        "content": "知识助手结果正文",
    }
    with patch(
        "app.services.ai.memory_service.memory_service.get_session_tool_artifact",
        new_callable=AsyncMock,
        return_value=None,
    ) as get_legacy, patch(
        "app.services.ai.memory_service.memory_service.get_reusable_result",
        new_callable=AsyncMock,
        return_value=unified,
    ) as get_unified:
        result = await load_session_tool_artifact("7", "conv-1")

    assert result == unified
    get_unified.assert_awaited_once_with("7", "conv-1")
    get_legacy.assert_not_awaited()


@pytest.mark.asyncio
async def test_assistant_artifact_loader_uses_legacy_only_when_unified_is_missing():
    legacy = {"tool_name": "legacy_tool", "text_excerpt": "旧结果"}
    with patch(
        "app.services.ai.memory_service.memory_service.get_reusable_result",
        new_callable=AsyncMock,
        return_value=None,
    ), patch(
        "app.services.ai.memory_service.memory_service.get_session_tool_artifact",
        new_callable=AsyncMock,
        return_value=legacy,
    ) as get_legacy:
        result = await load_session_tool_artifact("7", "conv-1")

    assert result == legacy
    get_legacy.assert_awaited_once_with("7", "conv-1")


@pytest.mark.asyncio
async def test_assistant_artifact_loader_falls_back_to_stack_when_current_is_invalid():
    invalid_current = {
        "result_id": "empty-current",
        "result_type": "generic",
        "structured": {"rows": []},
    }
    stacked = {
        "result_id": "stacked-1",
        "result_type": "generic",
        "content": "可复用的历史结果",
    }
    with patch(
        "app.services.ai.memory_service.memory_service.get_reusable_result",
        new_callable=AsyncMock,
        return_value=invalid_current,
    ), patch(
        "app.services.ai.memory_service.memory_service.get_reusable_result_stack",
        new_callable=AsyncMock,
        return_value=[stacked],
    ), patch(
        "app.services.ai.memory_service.memory_service.get_session_tool_artifact",
        new_callable=AsyncMock,
        return_value=None,
    ):
        result = await load_session_tool_artifact("7", "conv-1")

    assert result == stacked


@pytest.mark.asyncio
async def test_assistant_artifact_loader_prefers_selected_stack_item():
    current = {
        "result_id": "current-1",
        "result_type": "generic",
        "content": "当前结果",
    }
    selected = {
        "result_id": "selected-1",
        "result_type": "generic",
        "content": "用户明确选择的历史结果",
    }
    with patch(
        "app.services.ai.memory_service.memory_service.get_reusable_result",
        new_callable=AsyncMock,
        return_value=current,
    ), patch(
        "app.services.ai.memory_service.memory_service.get_reusable_result_stack",
        new_callable=AsyncMock,
        return_value=[selected],
    ):
        result = await load_session_tool_artifact(
            "7",
            "conv-1",
            preferred_result_id="selected-1",
        )

    assert result == selected


@pytest.mark.asyncio
async def test_assistant_artifact_loader_does_not_fall_back_to_current_for_missing_selection():
    current = {
        "result_id": "current-1",
        "result_type": "generic",
        "content": "当前结果",
    }
    with patch(
        "app.services.ai.memory_service.memory_service.get_reusable_result",
        new_callable=AsyncMock,
        return_value=current,
    ), patch(
        "app.services.ai.memory_service.memory_service.get_reusable_result_stack",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "app.services.ai.memory_service.memory_service.get_session_tool_artifact",
        new_callable=AsyncMock,
        return_value=None,
    ):
        result = await load_session_tool_artifact(
            "7",
            "conv-1",
            preferred_result_id="missing-1",
        )

    assert result is None


@pytest.mark.asyncio
async def test_assistant_artifact_loader_rejects_invalid_legacy_snapshot():
    legacy = {
        "result_id": "legacy-failed",
        "status": "failed",
        "text_excerpt": "工具失败，但仍有文本",
    }
    with patch(
        "app.services.ai.memory_service.memory_service.get_reusable_result",
        new_callable=AsyncMock,
        return_value=None,
    ), patch(
        "app.services.ai.memory_service.memory_service.get_session_tool_artifact",
        new_callable=AsyncMock,
        return_value=legacy,
    ):
        result = await load_session_tool_artifact("7", "conv-1")

    assert result is None


def test_assistant_prompt_can_force_injection_for_explicit_selected_result():
    artifact = {
        "result_id": "selected-1",
        "result_type": "generic",
        "text_excerpt": "用户明确选择的历史结果",
    }

    prompt = append_session_tool_artifact_to_system_prompt(
        "基础系统提示",
        "请整理成一份分析报告",
        artifact,
        force_reuse=True,
    )

    assert prompt.startswith("[上一轮可复用工具结果]")


def test_assistant_prompt_uses_cached_result_for_clicked_reply():
    artifact = {
        "result_id": "r1",
        "result_type": "generic",
        "origin_type": "sub_agent",
        "origin_name": "sub_agent_call",
        "text_excerpt": "这是上一轮子代理返回的结果。" * 20,
    }

    prompt = append_session_tool_artifact_to_system_prompt(
        "基础系统提示",
        "生成可视化分析报告\n\n---\n\n【被点击的 AI 回复】\n查询结果",
        artifact,
    )

    assert prompt.startswith("[上一轮可复用工具结果]")
    assert "sub_agent_call" in prompt
    assert "不要对同一工具重复" in prompt
