"""可复用结果列表接口的安全契约测试。"""

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.api.v1.endpoints import chat as chat_endpoint
from app.api.v1.endpoints.chat import ChatCompletionRequest
from app.services.ai.memory_service import memory_service
from app.core.orm import get_db_session


pytestmark = pytest.mark.no_infrastructure


def _fake_require_api_key(user_info):
    async def _inner():
        return user_info

    return _inner


class _FakeScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeSession:
    def __init__(self, *, conversation_owned: bool):
        self.conversation_owned = conversation_owned
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return _FakeScalarResult(1 if self.conversation_owned else None)


def _fake_db_session(*, conversation_owned: bool):
    session = _FakeSession(conversation_owned=conversation_owned)

    async def _inner():
        yield session

    return _inner, session


@pytest.mark.asyncio
async def test_list_reusable_results_returns_current_and_deduplicated_stack(monkeypatch):
    monkeypatch.setattr(
        memory_service,
        "get_reusable_result",
        AsyncMock(return_value={
            "result_id": "rr_2",
            "result_type": "data",
            "status": "success",
            "text_excerpt": "new result",
        }),
    )
    monkeypatch.setattr(
        memory_service,
        "get_reusable_result_stack",
        AsyncMock(return_value=[
            {
                "result_id": "rr_1",
                "result_type": "data",
                "status": "success",
                "text_excerpt": "old result",
            },
            {
                "result_id": "rr_2",
                "result_type": "data",
                "status": "success",
                "text_excerpt": "new result",
            },
        ]),
    )
    monkeypatch.setattr(memory_service, "get_last_data_result", AsyncMock(return_value=None))
    db_override, _ = _fake_db_session(conversation_owned=True)
    app.dependency_overrides[chat_endpoint.require_api_key] = _fake_require_api_key({"user_id": "7"})
    app.dependency_overrides[get_db_session] = db_override
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/v1/chat/reusable-results?conversation_id=conv-1",
                headers={"X-API-Key": "test-key"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    items = response.json()["data"]["items"]
    assert [item["result_id"] for item in items] == ["rr_2", "rr_1"]
    assert items[0]["is_current"] is True
    assert all("tool_args" not in item for item in items)


@pytest.mark.asyncio
async def test_list_reusable_results_includes_legacy_data_cache_during_migration(monkeypatch):
    monkeypatch.setattr(memory_service, "get_reusable_result", AsyncMock(return_value=None))
    monkeypatch.setattr(memory_service, "get_reusable_result_stack", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        memory_service,
        "get_last_data_result",
        AsyncMock(return_value={
            "rows": {"rows": [{"amount": 10}]},
            "saved_at": "2026-08-30T10:00:00+00:00",
            "dataset_name": "sales",
        }),
    )
    db_override, _ = _fake_db_session(conversation_owned=True)
    app.dependency_overrides[chat_endpoint.require_api_key] = _fake_require_api_key({"user_id": "7"})
    app.dependency_overrides[get_db_session] = db_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/chat/reusable-results?conversation_id=conv-1",
                headers={"X-API-Key": "test-key"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    items = response.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["result_type"] == "data"
    assert items[0]["is_current"] is True


@pytest.mark.asyncio
async def test_list_reusable_results_rejects_unowned_conversation(monkeypatch):
    monkeypatch.setattr(
        memory_service,
        "get_reusable_result",
        AsyncMock(return_value={
            "result_id": "rr-secret",
            "result_type": "data",
            "status": "success",
            "text_excerpt": "private result",
        }),
    )
    monkeypatch.setattr(memory_service, "get_reusable_result_stack", AsyncMock(return_value=[]))
    monkeypatch.setattr(memory_service, "get_last_data_result", AsyncMock(return_value=None))
    db_override, _ = _fake_db_session(conversation_owned=False)
    app.dependency_overrides[chat_endpoint.require_api_key] = _fake_require_api_key({"user_id": "7"})
    app.dependency_overrides[get_db_session] = db_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/chat/reusable-results?conversation_id=not-owned",
                headers={"X-API-Key": "test-key"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert "private result" not in response.text


@pytest.mark.asyncio
async def test_list_reusable_results_requires_stable_user_identity():
    app.dependency_overrides[chat_endpoint.require_api_key] = _fake_require_api_key({})
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/v1/chat/reusable-results?conversation_id=conv-1",
                headers={"X-API-Key": "test-key"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401


def test_chat_completion_request_accepts_bounded_reusable_result_id():
    request = ChatCompletionRequest(
        messages=[{"role": "user", "content": "继续分析"}],
        reusable_result_id="rr_old",
    )
    assert request.reusable_result_id == "rr_old"


def test_chat_completion_request_rejects_overlong_reusable_result_id():
    with pytest.raises(ValueError):
        ChatCompletionRequest(
            messages=[{"role": "user", "content": "继续分析"}],
            reusable_result_id="r" * 129,
        )
