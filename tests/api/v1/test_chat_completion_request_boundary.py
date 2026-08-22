import pytest
from fastapi import HTTPException

from app.api.v1.endpoints.chat import ChatMessage, validate_chat_completion_messages


pytestmark = pytest.mark.no_infrastructure


def test_validate_chat_completion_messages_accepts_current_user_message():
    validate_chat_completion_messages(
        [ChatMessage(role="user", content="本轮问题")],
        conversation_id="conversation-1",
    )


def test_validate_chat_completion_messages_rejects_assistant_as_last_message():
    with pytest.raises(HTTPException) as exc_info:
        validate_chat_completion_messages(
            [
                ChatMessage(role="user", content="旧问题"),
                ChatMessage(role="assistant", content="旧回答"),
            ],
            conversation_id="conversation-1",
        )

    assert exc_info.value.status_code == 400
    assert "最后一条消息" in str(exc_info.value.detail)


def test_validate_chat_completion_messages_rejects_blank_current_user_message():
    with pytest.raises(HTTPException) as exc_info:
        validate_chat_completion_messages(
            [ChatMessage(role="user", content="  ")],
            conversation_id="conversation-1",
        )

    assert exc_info.value.status_code == 400
    assert "不能为空" in str(exc_info.value.detail)


def test_validate_chat_completion_messages_rejects_empty_messages():
    with pytest.raises(HTTPException) as exc_info:
        validate_chat_completion_messages([], conversation_id="conversation-1")

    assert exc_info.value.status_code == 400
