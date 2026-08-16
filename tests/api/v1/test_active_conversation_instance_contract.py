"""Active conversation API forwards the optional Embed instance scope."""

import pytest

from app.api.v1.endpoints import chat
from app.services.ai.memory_service import memory_service


pytestmark = pytest.mark.no_infrastructure


@pytest.mark.asyncio
async def test_get_active_conversation_forwards_instance_id(monkeypatch):
    calls = []

    async def fake_get(user_id, instance_id=None):
        calls.append((user_id, instance_id))
        return "conv-1"

    monkeypatch.setattr(memory_service, "get_active_conversation", fake_get)

    response = await chat.get_active_conversation(
        {"user_id": 7},
        instance_id="ops-assistant",
    )

    assert response.data["conversation_id"] == "conv-1"
    assert calls == [(7, "ops-assistant")]


@pytest.mark.asyncio
async def test_set_active_conversation_forwards_instance_id(monkeypatch):
    calls = []

    async def fake_set(user_id, conversation_id, instance_id=None):
        calls.append((user_id, conversation_id, instance_id))

    monkeypatch.setattr(memory_service, "set_active_conversation", fake_set)

    response = await chat.set_active_conversation(
        chat.ActiveConversationRequest(conversation_id="conv-2"),
        {"user_id": 7},
        instance_id="ops-assistant",
    )

    assert response.data["status"] == "success"
    assert calls == [(7, "conv-2", "ops-assistant")]
