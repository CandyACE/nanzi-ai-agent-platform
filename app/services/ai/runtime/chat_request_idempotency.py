from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_CHAT_REQUEST_IDEMPOTENCY_TTL_SECONDS = 24 * 60 * 60
MAX_CLIENT_REQUEST_ID_LENGTH = 128


@dataclass(frozen=True)
class ChatRequestClaim:
    key: str
    owner_token: str | None
    acquired: bool
    status: str
    trace_id: str | None = None


class ChatRequestIdempotencyStore:
    """用 Redis 记录聊天请求的短期幂等状态，避免网络重试再次启动模型任务。"""

    def __init__(self, ttl_seconds: int = DEFAULT_CHAT_REQUEST_IDEMPOTENCY_TTL_SECONDS):
        self.ttl_seconds = max(60, int(ttl_seconds))

    @staticmethod
    def _normalize_client_request_id(client_request_id: str | None) -> str:
        value = str(client_request_id or "").strip()
        if not value or len(value) > MAX_CLIENT_REQUEST_ID_LENGTH:
            return ""
        return value

    def _key(
        self,
        *,
        user_id: str | int,
        conversation_id: str,
        client_request_id: str,
    ) -> str:
        raw = f"{user_id}:{conversation_id}:{client_request_id}".encode("utf-8")
        digest = hashlib.sha256(raw).hexdigest()
        return f"nanzi:chat_request_idempotency:{digest}"

    @staticmethod
    def _decode_record(raw: Any) -> dict[str, Any]:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="ignore")
        try:
            record = json.loads(str(raw))
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return record if isinstance(record, dict) else {}

    async def claim(
        self,
        *,
        user_id: str | int,
        conversation_id: str | None,
        client_request_id: str | None,
    ) -> ChatRequestClaim | None:
        normalized_id = self._normalize_client_request_id(client_request_id)
        normalized_conversation_id = str(conversation_id or "").strip()
        if not normalized_id or not normalized_conversation_id:
            return None

        from app.core.redis import get_redis

        try:
            redis = await get_redis()
        except Exception as exc:
            logger.warning("[ChatRequestIdempotency] Redis unavailable: %s", exc)
            return None
        if redis is None:
            logger.warning("[ChatRequestIdempotency] Redis unavailable; skipping request claim")
            return None

        key = self._key(
            user_id=user_id,
            conversation_id=normalized_conversation_id,
            client_request_id=normalized_id,
        )
        owner_token = uuid.uuid4().hex
        processing_record = json.dumps(
            {"status": "processing", "owner_token": owner_token, "trace_id": None},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        try:
            acquired = await redis.set(
                key,
                processing_record,
                ex=self.ttl_seconds,
                nx=True,
            )
            if acquired:
                return ChatRequestClaim(
                    key=key,
                    owner_token=owner_token,
                    acquired=True,
                    status="processing",
                )

            record = self._decode_record(await redis.get(key))
            return ChatRequestClaim(
                key=key,
                owner_token=None,
                acquired=False,
                status=str(record.get("status") or "processing"),
                trace_id=self._safe_trace_id(record.get("trace_id")),
            )
        except Exception as exc:
            logger.warning("[ChatRequestIdempotency] claim failed: %s", exc)
            return None

    async def finish(
        self,
        claim: ChatRequestClaim | None,
        *,
        status: str,
        trace_id: str | None = None,
    ) -> None:
        if not claim or not claim.acquired or not claim.owner_token:
            return
        if status not in {"completed", "failed"}:
            status = "failed"

        from app.core.redis import get_redis

        try:
            redis = await get_redis()
        except Exception as exc:
            logger.warning("[ChatRequestIdempotency] Redis unavailable during finish: %s", exc)
            return
        if redis is None:
            return
        replacement = json.dumps(
            {
                "status": status,
                "owner_token": claim.owner_token,
                "trace_id": self._safe_trace_id(trace_id),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        script = (
            "if redis.call('get', KEYS[1]) == ARGV[1] then "
            "redis.call('set', KEYS[1], ARGV[2], 'EX', ARGV[3]) return 1 "
            "else return 0 end"
        )
        try:
            await redis.eval(
                script,
                1,
                claim.key,
                self._processing_value(claim),
                replacement,
                self.ttl_seconds,
            )
        except Exception as exc:
            logger.warning("[ChatRequestIdempotency] finish failed: %s", exc)

    @staticmethod
    def _safe_trace_id(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text or len(text) > 128:
            return None
        try:
            uuid.UUID(text)
        except (TypeError, ValueError, AttributeError):
            return None
        return text

    @staticmethod
    def _processing_value(claim: ChatRequestClaim) -> str:
        return json.dumps(
            {"status": "processing", "owner_token": claim.owner_token, "trace_id": None},
            ensure_ascii=False,
            separators=(",", ":"),
        )


chat_request_idempotency = ChatRequestIdempotencyStore()
