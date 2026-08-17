"""Regression tests for the server-side user-question cancellation short circuit."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.services.ai.agent_service import AgentService


pytestmark = pytest.mark.no_infrastructure


@pytest.mark.asyncio
async def test_cancelled_user_question_stops_before_agent_resolution():
    class FakeQuestionStore:
        async def submit_answer(self, **kwargs):
            assert kwargs["cancelled"] is True
            return {"status": "cancelled"}

    service = AgentService()
    receipt = (
        "【用户回答】\n"
        "interaction_type: question\n"
        "question_id: uq_cancel\n"
        "selected_option_ids: []\n"
        "custom_input: \n"
        "cancelled: true"
    )

    with (
        patch.object(service, "_quota_block_message", AsyncMock(return_value=None)),
        patch(
            "app.services.ai.agent_service.memory_service.get_history",
            AsyncMock(return_value=[]),
        ) as get_history,
        patch(
            "app.services.ai.agent_service.memory_service.add_message",
            AsyncMock(),
        ) as add_message,
        patch(
            "app.services.ai.user_question_store.UserQuestionStore.from_runtime",
            AsyncMock(return_value=FakeQuestionStore()),
        ),
        patch(
            "app.services.ai.context_manager.AgentContextManager.resolve_agent_config",
            AsyncMock(),
        ) as resolve_agent_config,
        patch(
            "app.services.ai.agent_service.AuditManager.log_transaction",
            AsyncMock(),
        ),
        patch(
            "app.services.config_service.ConfigService.get",
            AsyncMock(return_value="20"),
        ),
        patch(
            "app.core.redis.get_redis",
            AsyncMock(return_value=None),
        ),
    ):
        chunks = [
            chunk
            async for chunk in service.chat_completion_stream(
                [{"role": "user", "content": receipt}],
                conversation_id="conversation-cancel",
                user_info={"user_id": "100", "role": "admin"},
                enable_multi_agent=False,
            )
        ]

    assert chunks[-1]["content"] == "已取消本次提问，本次任务已停止。"
    assert chunks[-1]["status"] == "success"
    resolve_agent_config.assert_not_awaited()
    get_history.assert_awaited_once()
    await asyncio.sleep(0)
    assert add_message.await_count == 2
