import uuid

import pytest

from app.services.ai.runtime.chat_request_idempotency import (
    ChatRequestIdempotencyStore,
)

pytestmark = pytest.mark.no_infrastructure


class FakeRedis:
    def __init__(self):
        self.store: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self.store:
            return False
        self.store[key] = value
        if ex is not None:
            self.ttls[key] = int(ex)
        return True

    async def get(self, key):
        return self.store.get(key)

    async def eval(self, _script, _numkeys, key, owner, replacement, ttl):
        if self.store.get(key) != owner:
            return 0
        self.store[key] = replacement
        self.ttls[key] = int(ttl)
        return 1


@pytest.mark.asyncio
async def test_first_claim_wins_and_completion_is_reusable(monkeypatch):
    fake = FakeRedis()

    async def _redis():
        return fake

    monkeypatch.setattr("app.core.redis.get_redis", _redis)
    store = ChatRequestIdempotencyStore(ttl_seconds=900)

    first = await store.claim(user_id="u1", conversation_id="c1", client_request_id="req-1")
    duplicate = await store.claim(user_id="u1", conversation_id="c1", client_request_id="req-1")

    assert first is not None and first.acquired is True
    assert duplicate is not None and duplicate.acquired is False
    assert duplicate.status == "processing"
    trace_id = str(uuid.uuid4())
    await store.finish(first, status="completed", trace_id=trace_id)
    completed = await store.claim(user_id="u1", conversation_id="c1", client_request_id="req-1")
    assert completed is not None
    assert completed.acquired is False
    assert completed.status == "completed"
    assert completed.trace_id == trace_id
    assert fake.ttls[first.key] == 900


@pytest.mark.asyncio
async def test_request_identity_isolated_by_user_and_conversation(monkeypatch):
    fake = FakeRedis()

    async def _redis():
        return fake

    monkeypatch.setattr("app.core.redis.get_redis", _redis)
    store = ChatRequestIdempotencyStore()
    first = await store.claim(user_id="u1", conversation_id="c1", client_request_id="same")
    other_user = await store.claim(user_id="u2", conversation_id="c1", client_request_id="same")
    other_conversation = await store.claim(user_id="u1", conversation_id="c2", client_request_id="same")
    assert first and other_user and other_conversation
    assert first.key != other_user.key != other_conversation.key
    assert other_user.acquired is True
    assert other_conversation.acquired is True


@pytest.mark.asyncio
async def test_unavailable_redis_fails_open_and_invalid_id_is_ignored(monkeypatch):
    async def _redis():
        return None

    monkeypatch.setattr("app.core.redis.get_redis", _redis)
    store = ChatRequestIdempotencyStore()
    assert await store.claim(user_id="u1", conversation_id="c1", client_request_id="req") is None
    assert await store.claim(user_id="u1", conversation_id="c1", client_request_id=" ") is None
    assert await store.claim(user_id="u1", conversation_id=None, client_request_id="req") is None
