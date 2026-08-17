"""Tests for pending user-question state and answer validation."""
from __future__ import annotations

import pytest

from app.services.ai.user_question_store import UserQuestionStore


pytestmark = pytest.mark.no_infrastructure


@pytest.mark.asyncio
async def test_pending_question_is_scoped_and_submit_is_idempotent():
    store = UserQuestionStore(redis_client=None)
    await store.create_pending(
        user_id=100,
        conversation_id="conversation-1",
        question_id="uq_1",
        payload={
            "question": "选择维度",
            "options": [{"id": "daily"}, {"id": "monthly"}],
            "is_multi_select": False,
            "allow_custom_input": True,
        },
    )

    pending = await store.get_pending(
        user_id=100,
        conversation_id="conversation-1",
        question_id="uq_1",
    )
    assert pending is not None
    assert pending["status"] == "pending"

    submitted = await store.submit_answer(
        user_id=100,
        conversation_id="conversation-1",
        question_id="uq_1",
        selected_option_ids=["monthly"],
        custom_input="排除退款",
    )
    assert submitted["status"] == "submitted"
    assert submitted["selected_option_ids"] == ["monthly"]

    repeated = await store.submit_answer(
        user_id=100,
        conversation_id="conversation-1",
        question_id="uq_1",
        selected_option_ids=["monthly"],
        custom_input="排除退款",
    )
    assert repeated == submitted


@pytest.mark.asyncio
async def test_pending_question_rejects_wrong_scope_and_invalid_answer():
    store = UserQuestionStore(redis_client=None)
    await store.create_pending(
        user_id=100,
        conversation_id="conversation-1",
        question_id="uq_2",
        payload={
            "question": "选择维度",
            "options": [{"id": "daily"}, {"id": "monthly"}],
            "is_multi_select": False,
            "allow_custom_input": False,
        },
    )

    with pytest.raises(PermissionError):
        await store.submit_answer(
            user_id=101,
            conversation_id="conversation-1",
            question_id="uq_2",
            selected_option_ids=["daily"],
        )

    with pytest.raises(ValueError):
        await store.submit_answer(
            user_id=100,
            conversation_id="conversation-1",
            question_id="uq_2",
            selected_option_ids=["unknown"],
        )

    with pytest.raises(ValueError):
        await store.submit_answer(
            user_id=100,
            conversation_id="conversation-1",
            question_id="uq_2",
            selected_option_ids=["daily", "monthly"],
        )


@pytest.mark.asyncio
async def test_pending_question_expiry_and_one_active_question_per_conversation():
    store = UserQuestionStore(redis_client=None)
    await store.create_pending(
        user_id=200,
        conversation_id="conversation-expiry",
        question_id="uq_expired",
        payload={"question": "选择", "options": [{"id": "a"}, {"id": "b"}]},
    )
    # 创建新问题会自动覆盖旧的待回答问题
    second = await store.create_pending(
        user_id=200,
        conversation_id="conversation-expiry",
        question_id="uq_second",
        payload={"question": "再次选择", "options": [{"id": "a"}, {"id": "b"}]},
    )
    assert second["status"] == "pending"
    old_record = await store._get(store._key(200, "conversation-expiry", "uq_expired"))
    assert old_record["status"] == "superseded"

    key = store._key(200, "conversation-expiry", "uq_expired")
    store._memory[key]["expires_at"] = 0
    assert await store.get_pending(
        user_id=200,
        conversation_id="conversation-expiry",
        question_id="uq_expired",
    ) is None


@pytest.mark.asyncio
async def test_pending_question_can_be_cancelled_without_an_answer():
    store = UserQuestionStore(redis_client=None)
    await store.create_pending(
        user_id=300,
        conversation_id="conversation-cancel",
        question_id="uq_cancel",
        payload={
            "question": "选择维度",
            "options": [{"id": "daily"}, {"id": "monthly"}],
        },
    )

    cancelled = await store.submit_answer(
        user_id=300,
        conversation_id="conversation-cancel",
        question_id="uq_cancel",
        selected_option_ids=[],
        cancelled=True,
    )

    assert cancelled["status"] == "cancelled"
    assert cancelled["selected_option_ids"] == []
    assert cancelled["custom_input"] == ""
    assert await store.get_pending(
        user_id=300,
        conversation_id="conversation-cancel",
        question_id="uq_cancel",
    ) is None

    repeated = await store.submit_answer(
        user_id=300,
        conversation_id="conversation-cancel",
        question_id="uq_cancel",
        selected_option_ids=["monthly"],
        custom_input="不应覆盖取消状态",
    )
    assert repeated == cancelled
