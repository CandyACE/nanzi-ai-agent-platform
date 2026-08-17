"""Pending state and answer validation for AI-initiated user questions."""
from __future__ import annotations

import copy
import json
import time
from contextlib import asynccontextmanager
from asyncio import Lock
from typing import Any


_MEMORY_STORE: dict[str, dict[str, Any]] = {}
_MEMORY_LOCKS: dict[str, Lock] = {}


class UserQuestionStore:
    """Store pending questions in Redis or an explicit process-local test store."""

    KEY_PREFIX = "ai:user-question"
    DEFAULT_TTL_SECONDS = 900

    def __init__(
        self,
        redis_client: Any = None,
        *,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        allow_memory_fallback: bool = True,
    ):
        self.redis_client = redis_client
        self.ttl_seconds = max(60, int(ttl_seconds))
        self.allow_memory_fallback = allow_memory_fallback
        self._memory = _MEMORY_STORE

    @classmethod
    async def from_runtime(cls) -> "UserQuestionStore":
        from app.core.redis import get_redis

        return cls(await get_redis(), allow_memory_fallback=False)

    @classmethod
    def _key(cls, user_id: int | str, conversation_id: str, question_id: str) -> str:
        return f"{cls.KEY_PREFIX}:{user_id}:{conversation_id}:{question_id}"

    @classmethod
    def _active_key(cls, user_id: int | str, conversation_id: str) -> str:
        return f"{cls.KEY_PREFIX}:active:{user_id}:{conversation_id}"

    async def create_pending(
        self,
        *,
        user_id: int | str,
        conversation_id: str,
        question_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        key = self._key(user_id, conversation_id, question_id)
        active_key = self._active_key(user_id, conversation_id)
        async with self._submission_lock(active_key):
            active = await self._get(active_key)
            if active and active.get("status") == "pending" and not self._is_expired(active):
                old_qid = active.get("question_id")
                if old_qid and old_qid != question_id:
                    old_key = self._key(user_id, conversation_id, old_qid)
                    old_record = await self._get(old_key)
                    if old_record and old_record.get("status") == "pending":
                        old_record["status"] = "superseded"
                        await self._set(old_key, old_record)
            record = {
                **copy.deepcopy(payload),
                "question_id": question_id,
                "user_id": str(user_id),
                "conversation_id": conversation_id,
                "status": "pending",
                "created_at": int(time.time()),
                "expires_at": int(time.time()) + self.ttl_seconds,
            }
            await self._set(key, record)
            await self._set(
                active_key,
                {
                    "question_id": question_id,
                    "status": "pending",
                    "expires_at": record["expires_at"],
                },
            )
        return copy.deepcopy(record)

    async def get_pending(
        self,
        *,
        user_id: int | str,
        conversation_id: str,
        question_id: str,
    ) -> dict[str, Any] | None:
        record = await self._get(self._key(user_id, conversation_id, question_id))
        if not record:
            return None
        if record.get("status") != "pending":
            return None
        if self._is_expired(record):
            record["status"] = "expired"
            await self._set(self._key(user_id, conversation_id, question_id), record)
            return None
        return copy.deepcopy(record)

    async def submit_answer(
        self,
        *,
        user_id: int | str,
        conversation_id: str,
        question_id: str,
        selected_option_ids: list[str],
        custom_input: str = "",
        cancelled: bool = False,
    ) -> dict[str, Any]:
        key = self._key(user_id, conversation_id, question_id)
        active_key = self._active_key(user_id, conversation_id)
        async with self._submission_lock(key):
            record = await self._get(key)
            if record is None:
                raise PermissionError("问题不存在或不属于当前会话")
            if record.get("status") == "submitted":
                return copy.deepcopy(record)
            if record.get("status") == "cancelled":
                return copy.deepcopy(record)
            if record.get("status") != "pending" or self._is_expired(record):
                raise ValueError("问题已过期，无法提交回答")

            selected = [str(item).strip() for item in selected_option_ids if str(item).strip()]
            if cancelled:
                record.update(
                    {
                        "status": "cancelled",
                        "selected_option_ids": [],
                        "custom_input": "",
                        "cancelled_at": int(time.time()),
                    }
                )
                await self._set(key, record)
                await self._delete(active_key)
                return copy.deepcopy(record)
            if len(selected) != len(set(selected)):
                raise ValueError("不能重复选择同一选项")
            allowed = {
                str(option.get("id"))
                for option in record.get("options", [])
                if isinstance(option, dict) and str(option.get("id") or "").strip()
            }
            if not set(selected).issubset(allowed):
                raise ValueError("回答包含无效选项")
            if not record.get("is_multi_select") and len(selected) > 1:
                raise ValueError("单选问题只能选择一个选项")
            normalized_custom_input = str(custom_input or "").strip()
            if normalized_custom_input and not record.get("allow_custom_input", True):
                raise ValueError("当前问题不允许补充输入")
            if not selected and not normalized_custom_input:
                raise ValueError("至少选择一个选项或填写补充说明")
            record.update(
                {
                    "status": "submitted",
                    "selected_option_ids": selected,
                    "custom_input": normalized_custom_input,
                    "submitted_at": int(time.time()),
                }
            )
            await self._set(key, record)
            await self._delete(active_key)
            return copy.deepcopy(record)

    @staticmethod
    def _is_expired(record: dict[str, Any]) -> bool:
        return int(record.get("expires_at") or 0) <= int(time.time())

    async def _get(self, key: str) -> dict[str, Any] | None:
        if self.redis_client is None:
            if not self.allow_memory_fallback:
                raise RuntimeError("Redis is required for user-question state")
            return copy.deepcopy(self._memory.get(key))
        raw = await self.redis_client.get(key)
        if not raw:
            return None
        return json.loads(raw)

    async def _set(self, key: str, value: dict[str, Any]) -> None:
        if self.redis_client is None:
            if not self.allow_memory_fallback:
                raise RuntimeError("Redis is required for user-question state")
            self._memory[key] = copy.deepcopy(value)
            return
        await self.redis_client.set(
            key,
            json.dumps(value, ensure_ascii=False),
            ex=self.ttl_seconds,
        )

    async def _delete(self, key: str) -> None:
        if self.redis_client is None:
            if not self.allow_memory_fallback:
                raise RuntimeError("Redis is required for user-question state")
            self._memory.pop(key, None)
            return
        await self.redis_client.delete(key)

    @asynccontextmanager
    async def _submission_lock(self, key: str):
        if self.redis_client is not None:
            lock = self.redis_client.lock(f"{key}:lock", timeout=10, blocking_timeout=5)
            await lock.acquire()
            try:
                yield
            finally:
                await lock.release()
            return
        if not self.allow_memory_fallback:
            raise RuntimeError("Redis is required for user-question state")
        lock = _MEMORY_LOCKS.setdefault(key, Lock())
        async with lock:
            yield
