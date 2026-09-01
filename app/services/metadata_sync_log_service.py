"""元数据同步任务的临时日志与状态服务。"""

from __future__ import annotations

import json
import secrets
import time
from dataclasses import dataclass
from typing import Any

from app.core.redis import get_redis


@dataclass(frozen=True)
class SyncTask:
    task_id: str
    dataset_id: int
    status: str


class MetadataSyncLogService:
    """使用 Redis Hash + Stream 保存一个同步任务的短期状态和日志。"""

    TASK_KEY = "metadata_sync:task:{task_id}"
    STREAM_KEY = "metadata_sync:events:{task_id}"
    TASK_TTL_SECONDS = 1800
    STREAM_MAXLEN = 2000
    TERMINAL_EVENTS = frozenset({"completed", "failed"})

    def __init__(self, redis_client: Any | None = None):
        self._redis_client = redis_client

    async def _redis(self):
        if self._redis_client is not None:
            return self._redis_client
        return await get_redis()

    @classmethod
    def task_key(cls, task_id: str) -> str:
        return cls.TASK_KEY.format(task_id=task_id)

    @classmethod
    def stream_key(cls, task_id: str) -> str:
        return cls.STREAM_KEY.format(task_id=task_id)

    async def create_task(self, dataset_id: int) -> SyncTask:
        task_id = f"sync_{secrets.token_urlsafe(18)}"
        redis = await self._redis()
        await redis.hset(
            self.task_key(task_id),
            mapping={
                "dataset_id": str(dataset_id),
                "status": "running",
                "started_at_ms": str(int(time.time() * 1000)),
            },
        )
        await redis.expire(self.task_key(task_id), self.TASK_TTL_SECONDS)
        return SyncTask(task_id=task_id, dataset_id=dataset_id, status="running")

    async def get_task(self, task_id: str) -> dict[str, Any] | None:
        redis = await self._redis()
        values = await redis.hgetall(self.task_key(task_id))
        if not values:
            return None
        result = dict(values)
        if "dataset_id" in result:
            result["dataset_id"] = int(result["dataset_id"])
        if "started_at_ms" in result:
            result["started_at_ms"] = int(result["started_at_ms"])
        return result

    async def belongs_to_dataset(self, task_id: str, dataset_id: int) -> bool:
        task = await self.get_task(task_id)
        return bool(task and task.get("dataset_id") == dataset_id)

    async def publish(
        self,
        task_id: str,
        *,
        event: str,
        stage: str,
        message: str,
        progress: int | None = None,
        completed_documents: int | None = None,
        total_documents: int | None = None,
        error_detail: str | None = None,
    ) -> dict[str, Any]:
        if event in self.TERMINAL_EVENTS and stage != event:
            raise ValueError("终态事件的 stage 必须与 event 一致")
        if event not in {"started", "progress", *self.TERMINAL_EVENTS}:
            raise ValueError(f"不支持的同步日志事件: {event}")

        task = await self.get_task(task_id)
        if not task:
            raise ValueError(f"同步任务不存在: {task_id}")

        elapsed_ms = max(0, int(time.time() * 1000) - task["started_at_ms"])
        payload: dict[str, Any] = {
            "task_id": task_id,
            "dataset_id": task["dataset_id"],
            "event": event,
            "stage": stage,
            "message": message,
            "progress": progress,
            "completed_documents": completed_documents,
            "total_documents": total_documents,
            "elapsed_ms": elapsed_ms,
        }
        if error_detail:
            payload["error_detail"] = error_detail

        redis = await self._redis()
        stream_fields = {"data": json.dumps(payload, ensure_ascii=False)}
        await redis.xadd(
            self.stream_key(task_id),
            stream_fields,
            maxlen=self.STREAM_MAXLEN,
            approximate=True,
        )
        await redis.expire(self.stream_key(task_id), self.TASK_TTL_SECONDS)

        if event in self.TERMINAL_EVENTS:
            await redis.hset(self.task_key(task_id), mapping={"status": event})
            await redis.expire(self.task_key(task_id), self.TASK_TTL_SECONDS)
        return payload

    async def read_events(
        self, task_id: str, *, after_id: str = "0-0", count: int | None = None
    ) -> list[dict[str, Any]]:
        redis = await self._redis()
        # XRANGE 的 min 默认包含边界；使用 exclusive ID 避免 SSE 重复发送上一条事件。
        entries = await redis.xrange(
            self.stream_key(task_id), min=f"({after_id}", max="+", count=count
        )
        events = []
        for entry_id, fields in entries:
            raw = fields.get("data")
            if raw is None:
                continue
            item = json.loads(raw)
            item["id"] = entry_id
            events.append(item)
        return events

    async def read_new_events(
        self, task_id: str, *, after_id: str, block_ms: int = 1000, count: int = 100
    ) -> list[dict[str, Any]]:
        """阻塞等待一批新事件；Redis 不可用时由调用方处理连接结束。"""
        redis = await self._redis()
        result = await redis.xread(
            {self.stream_key(task_id): after_id}, block=block_ms, count=count
        )
        events = []
        for _stream_name, entries in result or []:
            for entry_id, fields in entries:
                raw = fields.get("data")
                if raw is None:
                    continue
                item = json.loads(raw)
                item["id"] = entry_id
                events.append(item)
        return events


metadata_sync_log_service = MetadataSyncLogService()
