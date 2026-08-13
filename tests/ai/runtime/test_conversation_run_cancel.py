import asyncio
import time
import uuid

import pytest

from app.services.ai.runtime.conversation_run_cancel import (
    cancel_conversation_run,
    release_conversation_run_locks,
)
from app.services.ai.runtime.conversation_run_registry import (
    conversation_run_registry,
    track_conversation_run,
)

pytestmark = pytest.mark.no_infrastructure


class FakeRedis:
    def __init__(self):
        self.store: dict[str, str] = {}

    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self.store:
            return False
        self.store[key] = value
        return True

    async def delete(self, key):
        if key in self.store:
            del self.store[key]
            return 1
        return 0

    async def eval(self, script, numkeys, key, token):
        if self.store.get(key) == token:
            self.store.pop(key, None)
            return 1
        return 0

    async def scan_iter(self, match=None, count=50):
        prefix = (match or "").replace("*", "")
        for key in list(self.store.keys()):
            if key.startswith(prefix):
                yield key


@pytest.mark.asyncio
async def test_release_conversation_run_locks_clears_lane_and_session_locks(monkeypatch):
    fake = FakeRedis()
    conversation_id = f"conv-cancel-{uuid.uuid4().hex}"
    lane_key = f"nanzi:conv_run:u1:{conversation_id.replace(':', '_')}"
    session_key = f"conversation:u1:{conversation_id}:agent_lock:DataAgent"
    fake.store[lane_key] = "trace-1"
    fake.store[session_key] = "token-1"

    async def _redis():
        return fake

    monkeypatch.setattr("app.core.redis.get_redis", _redis)

    result = await release_conversation_run_locks(
        user_id="u1",
        conversation_id=conversation_id,
        trace_id="trace-1",
    )

    assert result["success"] is True
    assert result["lane_released"] is True
    assert result["session_locks_released"] == 1
    assert lane_key not in fake.store
    assert session_key not in fake.store


@pytest.mark.asyncio
async def test_release_conversation_run_locks_noop_without_conversation_id():
    result = await release_conversation_run_locks(
        user_id="u1",
        conversation_id=None,
    )
    assert result == {
        "success": False,
        "lane_released": False,
        "session_locks_released": 0,
    }


@pytest.fixture(autouse=True)
def _clear_run_registry():
    conversation_run_registry.clear()
    yield
    conversation_run_registry.clear()


@pytest.mark.asyncio
async def test_cancel_conversation_run_stops_task_and_releases_locks(monkeypatch):
    fake = FakeRedis()
    conversation_id = f"conv-cancel-{uuid.uuid4().hex}"
    lane_key = f"nanzi:conv_run:u1:{conversation_id.replace(':', '_')}"
    fake.store[lane_key] = "trace-1"

    async def _redis():
        return fake

    monkeypatch.setattr("app.core.redis.get_redis", _redis)

    started = asyncio.Event()

    async def _long_run():
        async with track_conversation_run("u1", conversation_id):
            started.set()
            await asyncio.sleep(30)

    task = asyncio.create_task(_long_run())
    await asyncio.wait_for(started.wait(), timeout=1)
    t0 = time.monotonic()

    result = await cancel_conversation_run(
        user_id="u1",
        conversation_id=conversation_id,
        trace_id="trace-1",
    )

    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=2)

    assert result["success"] is True
    assert result["run_cancelled"] is True
    assert result["lane_released"] is True
    assert lane_key not in fake.store
    assert time.monotonic() - t0 < 5


@pytest.mark.asyncio
async def test_cancel_conversation_run_reports_false_when_nothing_is_running(monkeypatch):
    async def _redis():
        return FakeRedis()

    monkeypatch.setattr("app.core.redis.get_redis", _redis)

    result = await cancel_conversation_run(
        user_id="u1",
        conversation_id="conv-missing",
    )
    assert result["run_cancelled"] is False
    assert result["canvas_stopped"] == 0
    assert result["success"] is False
