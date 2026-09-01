import pytest

from app.api.portal.endpoints import metadata


pytestmark = pytest.mark.no_infrastructure


class FakeLogService:
    TERMINAL_EVENTS = frozenset({"completed", "failed"})

    async def belongs_to_dataset(self, task_id, dataset_id):
        return task_id == "sync_test" and dataset_id == 17

    async def read_events(self, task_id, *, after_id):
        if after_id == "0-0":
            return [
                {"id": "1-0", "event": "started", "stage": "queued", "message": "同步任务已开始", "progress": 0},
                {"id": "2-0", "event": "completed", "stage": "completed", "message": "同步成功", "progress": 100},
            ]
        return []

    async def read_new_events(self, task_id, *, after_id, block_ms):
        return []


@pytest.mark.asyncio
async def test_metadata_sync_events_replays_and_streams_events(monkeypatch):
    monkeypatch.setattr(metadata, "metadata_sync_log_service", FakeLogService())

    response = await metadata.metadata_sync_events(17, "sync_test")
    chunks = [chunk async for chunk in response.body_iterator]
    content = b"".join(chunk if isinstance(chunk, bytes) else chunk.encode() for chunk in chunks).decode()

    assert response.media_type == "text/event-stream"
    assert "event: started" in content
    assert "event: completed" in content
    assert '"progress": 100' in content


@pytest.mark.asyncio
async def test_metadata_sync_events_rejects_wrong_dataset(monkeypatch):
    monkeypatch.setattr(metadata, "metadata_sync_log_service", FakeLogService())

    with pytest.raises(Exception) as exc_info:
        await metadata.metadata_sync_events(18, "sync_test")

    assert getattr(exc_info.value, "status_code", None) == 404


def test_sync_endpoint_returns_task_id_and_declares_sse_route():
    source = open("app/api/portal/endpoints/metadata.py", encoding="utf-8").read()

    assert '"task_id": task.task_id' in source
    assert "/rag/sync/{task_id}/events" in source
    assert "X-Accel-Buffering" in source
