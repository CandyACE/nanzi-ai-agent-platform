"""会话级项目资源范围：仅保存用户主动挂载的资源。"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Iterable

from app.core.redis import get_redis


class ConversationResourceService:
    KEY_PREFIX = "conversation"
    SUFFIX = "resource_scope_v1"
    _LIST_KEYS = ("datasets", "knowledge_bases", "skills", "mcp_tools")

    @classmethod
    def _key(cls, user_id: Any, conversation_id: str) -> str:
        return f"{cls.KEY_PREFIX}:{user_id or 'anonymous'}:{conversation_id}:{cls.SUFFIX}"

    @classmethod
    def _empty_scope(cls) -> Dict[str, Any]:
        return {
            "project_name": "",
            "datasets": [],
            "knowledge_bases": [],
            "skills": [],
            "mcp_tools": [],
        }

    @classmethod
    def _decode_scope(cls, raw: Any) -> Dict[str, Any]:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        try:
            value = json.loads(raw or "{}")
        except (TypeError, ValueError):
            value = {}
        if not isinstance(value, dict):
            value = {}
        result: Dict[str, Any] = {"project_name": str(value.get("project_name") or "").strip()}
        result.update({
            key: [item for item in value.get(key, []) if isinstance(item, dict)]
            for key in cls._LIST_KEYS
        })
        return result

    @classmethod
    async def get(cls, user_id: Any, conversation_id: str) -> Dict[str, Any]:
        try:
            redis = await get_redis()
        except Exception:
            redis = None
        if not redis:
            return cls._empty_scope()
        try:
            raw = await redis.get(cls._key(user_id, conversation_id))
        except Exception:
            return cls._empty_scope()
        return cls._decode_scope(raw)

    @classmethod
    async def get_many(cls, user_id: Any, conversation_ids: Iterable[str]) -> Dict[str, Dict[str, Any]]:
        """批量读取会话范围，历史列表不要为每条记录单独访问 Redis。"""
        ids = [str(item) for item in conversation_ids if str(item or "").strip()]
        if not ids:
            return {}
        try:
            redis = await get_redis()
        except Exception:
            redis = None
        if not redis:
            return {cid: cls._empty_scope() for cid in ids}
        keys = [cls._key(user_id, cid) for cid in ids]
        try:
            if hasattr(redis, "mget"):
                raw_values = await redis.mget(keys)
            else:
                raw_values = [await redis.get(key) for key in keys]
        except Exception:
            return {cid: cls._empty_scope() for cid in ids}
        return {
            cid: cls._decode_scope(raw)
            for cid, raw in zip(ids, raw_values)
        }

    @classmethod
    async def get_many_for_owners(
        cls,
        owner_conversations: Iterable[tuple[Any, str]],
    ) -> Dict[tuple[str, str], Dict[str, Any]]:
        """按归属用户批量读取范围，供管理员历史列表使用。"""
        pairs = [(str(owner), str(cid)) for owner, cid in owner_conversations if str(cid or "").strip()]
        if not pairs:
            return {}
        try:
            redis = await get_redis()
        except Exception:
            redis = None
        if not redis:
            return {(owner, cid): cls._empty_scope() for owner, cid in pairs}
        keys = [cls._key(owner, cid) for owner, cid in pairs]
        try:
            raw_values = await redis.mget(keys) if hasattr(redis, "mget") else [await redis.get(key) for key in keys]
        except Exception:
            return {(owner, cid): cls._empty_scope() for owner, cid in pairs}
        return {
            pair: cls._decode_scope(raw)
            for pair, raw in zip(pairs, raw_values)
        }

    @classmethod
    async def replace(cls, user_id: Any, conversation_id: str, scope: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        normalized: Dict[str, Any] = {"project_name": str(scope.get("project_name") or "").strip()[:100]}
        normalized.update({
            key: [item for item in scope.get(key, []) if isinstance(item, dict) and item.get("id")]
            for key in cls._LIST_KEYS
        })
        try:
            redis = await get_redis()
            if redis:
                await redis.set(cls._key(user_id, conversation_id), json.dumps(normalized, ensure_ascii=False), ex=604800)
        except Exception:
            pass
        return normalized

    @classmethod
    async def delete(cls, user_id: Any, conversation_id: str) -> None:
        try:
            redis = await get_redis()
            if redis:
                await redis.delete(cls._key(user_id, conversation_id))
        except Exception:
            pass
