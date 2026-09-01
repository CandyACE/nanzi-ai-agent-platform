"""基于 Redis 的在线用户活跃状态。"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from app.core.redis import get_redis


ONLINE_PRESENCE_ZSET_KEY = "presence:users"
ONLINE_PRESENCE_HASH_PREFIX = "presence:user:"
ONLINE_PRESENCE_TOUCH_PREFIX = "presence:touch:"
ONLINE_PRESENCE_TTL_SECONDS = 300
ONLINE_PRESENCE_TOUCH_INTERVAL_SECONDS = 30


def _as_text(value: Any) -> str:
    """统一处理 Redis decode_responses 和测试客户端可能返回的值。"""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value) if value is not None else ""


class OnlinePresenceService:
    """维护按用户聚合的短期活跃状态，不参与认证授权。"""

    @classmethod
    async def touch(
        cls,
        user_info: Dict[str, Any],
        *,
        redis_client: Any = None,
        now: Optional[int] = None,
    ) -> bool:
        """记录用户活跃状态；同一用户最多每 30 秒写入一次。"""
        user_id = _as_text(user_info.get("user_id")).strip()
        if not user_id:
            return False

        redis = redis_client or await get_redis()
        if not redis:
            return False

        touch_key = f"{ONLINE_PRESENCE_TOUCH_PREFIX}{user_id}"
        acquired = await redis.set(
            touch_key,
            "1",
            ex=ONLINE_PRESENCE_TOUCH_INTERVAL_SECONDS,
            nx=True,
        )
        if not acquired:
            return False

        timestamp = int(time.time() if now is None else now)
        expires_at = timestamp + ONLINE_PRESENCE_TTL_SECONDS
        mapping = {
            "user_id": user_id,
            "user_name": _as_text(user_info.get("user_name")),
            "real_name": _as_text(user_info.get("real_name"))
            or _as_text(user_info.get("user_name")),
            "role": _as_text(user_info.get("role")),
            "last_active": str(timestamp),
        }

        pipe = redis.pipeline()
        pipe.zadd(ONLINE_PRESENCE_ZSET_KEY, {user_id: expires_at})
        pipe.hset(f"{ONLINE_PRESENCE_HASH_PREFIX}{user_id}", mapping=mapping)
        pipe.expire(
            f"{ONLINE_PRESENCE_HASH_PREFIX}{user_id}",
            ONLINE_PRESENCE_TTL_SECONDS * 2,
        )
        await pipe.execute()
        return True

    @classmethod
    async def list_active_users(
        cls,
        *,
        redis_client: Any = None,
        now: Optional[int] = None,
    ) -> list[dict[str, str]]:
        """清理过期状态并返回按最近活跃时间倒序排列的用户列表。"""
        redis = redis_client or await get_redis()
        if not redis:
            return []

        timestamp = int(time.time() if now is None else now)
        await redis.zremrangebyscore(
            ONLINE_PRESENCE_ZSET_KEY,
            "-inf",
            timestamp,
        )
        user_ids = await redis.zrange(ONLINE_PRESENCE_ZSET_KEY, 0, -1)
        if not user_ids:
            return []

        pipe = redis.pipeline()
        for user_id in user_ids:
            pipe.hgetall(f"{ONLINE_PRESENCE_HASH_PREFIX}{_as_text(user_id)}")
        hash_results = await pipe.execute()

        active_users: list[dict[str, str]] = []
        missing_user_ids: list[str] = []
        for user_id, user_data in zip(user_ids, hash_results):
            normalized_user_id = _as_text(user_id)
            if not user_data:
                missing_user_ids.append(normalized_user_id)
                continue

            try:
                last_active = int(_as_text(user_data.get("last_active")))
            except (TypeError, ValueError):
                missing_user_ids.append(normalized_user_id)
                continue

            if last_active + ONLINE_PRESENCE_TTL_SECONDS <= timestamp:
                missing_user_ids.append(normalized_user_id)
                continue

            normalized_data = {
                _as_text(key): _as_text(value)
                for key, value in user_data.items()
            }
            normalized_data.setdefault("user_id", normalized_user_id)
            active_users.append(normalized_data)

        if missing_user_ids:
            await redis.zrem(ONLINE_PRESENCE_ZSET_KEY, *missing_user_ids)

        active_users.sort(
            key=lambda item: int(item.get("last_active", "0")),
            reverse=True,
        )
        return active_users
