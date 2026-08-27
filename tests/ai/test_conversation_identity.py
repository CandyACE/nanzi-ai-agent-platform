import pytest
from fastapi import HTTPException
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.ai.context_compaction_log_service import ContextCompactionLogService
from app.services.ai.conversation_identity import (
    MissingUserIdentityError,
    require_user_id,
)
from app.services.ai.memory_service import MemoryService
from app.services.conversation_resource_service import ConversationResourceService


pytestmark = pytest.mark.no_infrastructure


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ({"user_id": 7}, "7"),
        ({"user_id": None, "id": 8}, "8"),
        ("user-9", "user-9"),
    ],
)
def test_require_user_id_normalizes_stable_identity(value, expected):
    assert require_user_id(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        None,
        {},
        object(),
        {"user_id": ""},
        {"user_id": "   "},
        {"user_id": "anonymous"},
        {"id": "anonymous"},
    ],
)
def test_require_user_id_fails_closed_instead_of_using_anonymous(value):
    with pytest.raises(MissingUserIdentityError):
        require_user_id(value)


@pytest.mark.parametrize(
    "key_builder",
    [
        lambda: MemoryService()._get_key(None, "conversation-1"),
        lambda: ConversationResourceService._key(None, "conversation-1"),
        lambda: ContextCompactionLogService.key(None, "conversation-1"),
    ],
)
def test_conversation_scoped_keys_never_fall_back_to_anonymous(key_builder):
    with pytest.raises(MissingUserIdentityError):
        key_builder()


@pytest.mark.asyncio
async def test_history_db_fallback_filters_by_user_id_and_conversation_id():
    from app.api.v1.endpoints.chat import get_conversation_history

    db_result = MagicMock()
    db_result.scalars.return_value.all.return_value = []
    db = MagicMock()
    db.execute = AsyncMock(return_value=db_result)

    with (
        patch(
            "app.services.ai.memory_service.memory_service.get_history",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "app.services.ai.agent_manager.AgentManagerService.list_agents",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        response = await get_conversation_history(
            "same-conversation-id",
            user_info={"user_id": 42, "user_name": "alice", "role": "admin"},
            db=db,
        )

    assert response.data.conversation_id == "same-conversation-id"
    query = db.execute.await_args.args[0]
    compiled_query = str(query)
    assert "conversation_id" in compiled_query
    assert "user_id" in compiled_query


@pytest.mark.asyncio
async def test_history_endpoint_rejects_missing_identity_before_memory_access():
    from app.api.v1.endpoints.chat import get_conversation_history

    with pytest.raises(HTTPException) as exc_info:
        await get_conversation_history(
            "conversation-1",
            user_info={"user_name": "alice"},
            db=MagicMock(),
        )

    assert exc_info.value.status_code == 401
