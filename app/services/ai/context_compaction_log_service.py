"""会话上下文压缩事件的 Redis 观测记录。

这类记录只用于 ChatLogs 的上下文时间线，不参与模型上下文拼装，
也不保存完整 prompt 或完整历史内容。
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.redis import get_redis


logger = logging.getLogger(__name__)


class ContextCompactionLogService:
    """按用户和会话保存上下文压缩事件的轻量 Redis LIST。"""

    KEY_PREFIX = "conversation"
    KEY_SUFFIX = "context_compactions_v1"
    TTL_SECONDS = 7 * 24 * 60 * 60
    MAX_RECORDS = 500
    PREVIEW_LIMIT = 300
    APPEND_TIMEOUT_SECONDS = 0.5

    @classmethod
    def key(cls, user_id: Any, conversation_id: str) -> str:
        uid = str(user_id) if user_id is not None and str(user_id) else "anonymous"
        return f"{cls.KEY_PREFIX}:{uid}:{conversation_id}:{cls.KEY_SUFFIX}"

    @classmethod
    def _normalize_record(
        cls,
        user_id: Any,
        conversation_id: str,
        record: Dict[str, Any],
    ) -> Dict[str, Any]:
        normalized = dict(record)
        normalized.setdefault("event_id", uuid.uuid4().hex)
        normalized.setdefault("conversation_id", str(conversation_id))
        normalized.setdefault(
            "occurred_at",
            datetime.now(timezone.utc).isoformat(),
        )
        preview = normalized.get("preview")
        if preview is not None:
            normalized["preview"] = str(preview)[: cls.PREVIEW_LIMIT]
        return normalized

    @classmethod
    def build_event_record(
        cls,
        event: Dict[str, Any],
        *,
        user_id: Any,
        conversation_id: str,
        trace_id: Optional[str] = None,
        source: str,
        stage: str,
        agent_name: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """把 SSE 事件裁剪成可长期保存的结构化记录。"""

        event_type = str(event.get("type") or "")
        preview = event.get("preview") or event.get("details") or ""
        record: Dict[str, Any] = {
            "event_id": uuid.uuid4().hex,
            "conversation_id": str(conversation_id),
            "event_type": event_type,
            "source": source,
            "stage": stage,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "title": str(event.get("title") or "上下文已压缩"),
            "status": str(event.get("status") or "success"),
            "preview": str(preview)[: cls.PREVIEW_LIMIT],
        }
        if trace_id:
            record["trace_id"] = str(trace_id)
        if agent_name:
            record["agent_name"] = str(agent_name)
        if model_name:
            record["model_name"] = str(model_name)

        # 只保留前端时间线需要的数值/来源元数据，避免把完整事件内容写入 Redis。
        for field in (
            "dropped",
            "kept",
            "origin",
            "token_used",
            "token_budget",
            "history_budget",
            "physical_window",
            "completion_reserve_tokens",
            "request_input_budget",
            "overhead_reservation_tokens",
            "prompt_overhead_reservation_tokens",
            "summary_chars",
        ):
            if field in event and event[field] is not None:
                record[field] = event[field]
        return record

    async def append(
        self,
        user_id: Any,
        conversation_id: str,
        record: Dict[str, Any],
    ) -> bool:
        if not user_id or not conversation_id or not isinstance(record, dict):
            return False

        try:
            redis = await get_redis()
        except Exception:
            logger.warning("Redis unavailable while appending context compaction record", exc_info=True)
            return False
        if not redis:
            return False

        key = self.key(user_id, conversation_id)
        payload = json.dumps(
            self._normalize_record(user_id, conversation_id, record),
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )
        try:
            async with redis.pipeline() as pipe:
                pipe.rpush(key, payload)
                pipe.ltrim(key, -self.MAX_RECORDS, -1)
                pipe.expire(key, self.TTL_SECONDS)
                await pipe.execute()
            return True
        except Exception:
            logger.warning(
                "Failed to append context compaction record key=%s",
                key,
                exc_info=True,
            )
            return False

    async def append_event(
        self,
        event: Dict[str, Any],
        *,
        user_id: Any,
        conversation_id: str,
        trace_id: Optional[str] = None,
        source: str,
        stage: str,
        agent_name: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> bool:
        record = self.build_event_record(
            event,
            user_id=user_id,
            conversation_id=conversation_id,
            trace_id=trace_id,
            source=source,
            stage=stage,
            agent_name=agent_name,
            model_name=model_name,
        )
        return await self.append(user_id, conversation_id, record)

    async def list_records(self, user_id: Any, conversation_id: str) -> List[Dict[str, Any]]:
        if not user_id or not conversation_id:
            return []

        try:
            redis = await get_redis()
        except Exception:
            logger.warning("Redis unavailable while reading context compaction records", exc_info=True)
            return []
        if not redis:
            return []

        key = self.key(user_id, conversation_id)
        try:
            raw_records = await redis.lrange(key, 0, -1)
        except Exception:
            logger.warning(
                "Failed to read context compaction records key=%s",
                key,
                exc_info=True,
            )
            return []

        records: List[Dict[str, Any]] = []
        for raw in raw_records or []:
            try:
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")
                record = json.loads(raw)
                if isinstance(record, dict):
                    records.append(record)
            except (TypeError, UnicodeDecodeError, json.JSONDecodeError):
                logger.warning("Skip malformed context compaction record key=%s", key)
        return records


context_compaction_log_service = ContextCompactionLogService()
