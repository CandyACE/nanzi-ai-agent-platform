import json
import logging
from typing import List, Dict, Any, Optional
from urllib.parse import quote
from app.core.redis import get_redis

logger = logging.getLogger(__name__)

class MemoryService:
    """
    Manages conversation history in Redis.
    Uses Redis LIST to store JSON-serialized messages.
    """
    
    # Key pattern: conversation:{user_id}:{conversation_id}:history
    KEY_PREFIX = "conversation"
    HISTORY_SUFFIX = "history"
    DATA_RESULT_SUFFIX = "last_data_result"
    DATA_RESULT_STACK_SUFFIX = "data_result_stack_v1"
    SESSION_TOOL_ARTIFACT_SUFFIX = "session_tool_artifact_v1"
    
    def __init__(self, max_history_turns: int = 50, ttl: int = 604800):
        """
        :param max_history_turns: Maximum number of dialogue turns (user + assistant) to keep.
        :param ttl: Time-to-live for the conversation in seconds (default 7 days).
        """
        self.max_history_len = max_history_turns * 2
        self.ttl = ttl

    def _get_key(self, user_id: str, conversation_id: str) -> str:
        """
        Generate Redis Key.
        Format: conversation:{user_id}:{conversation_id}:history
        """
        # Ensure user_id is string and handle potential None (fallback to 'anonymous' or error?)
        # For security, we should probably fail if user_id is missing, but for backward compat 
        # with loose validation systems, we safeguard str conversion.
        uid = str(user_id) if user_id else "anonymous" 
        return f"{self.KEY_PREFIX}:{uid}:{conversation_id}:{self.HISTORY_SUFFIX}"

    def _get_data_result_key(self, user_id: str, conversation_id: str) -> str:
        uid = str(user_id) if user_id else "anonymous"
        return f"{self.KEY_PREFIX}:{uid}:{conversation_id}:{self.DATA_RESULT_SUFFIX}"

    def _get_data_result_stack_key(self, user_id: str, conversation_id: str) -> str:
        uid = str(user_id) if user_id else "anonymous"
        return f"{self.KEY_PREFIX}:{uid}:{conversation_id}:{self.DATA_RESULT_STACK_SUFFIX}"

    def _get_session_tool_artifact_key(self, user_id: str, conversation_id: str) -> str:
        uid = str(user_id) if user_id else "anonymous"
        return f"{self.KEY_PREFIX}:{uid}:{conversation_id}:{self.SESSION_TOOL_ARTIFACT_SUFFIX}"

    async def get_data_result_stack(
        self,
        user_id: str,
        conversation_id: str,
    ) -> List[Dict[str, Any]]:
        redis = await get_redis()
        if not redis:
            return []
        key = self._get_data_result_stack_key(user_id, conversation_id)
        try:
            raw = await redis.get(key)
            if not raw:
                return []
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            parsed = json.loads(raw)
            return [item for item in parsed if isinstance(item, dict)] if isinstance(parsed, list) else []
        except Exception as e:
            logger.error("[MemoryService] Failed to get data result stack from key %s: %s", key, e)
            return []

    async def push_data_result_ref(
        self,
        user_id: str,
        conversation_id: str,
        payload: Dict[str, Any],
        *,
        max_depth: int = 10,
    ) -> None:
        from app.services.ai.chatbi_result_stack import ChatBIResultRef, push_result_ref

        redis = await get_redis()
        if not redis:
            logger.warning("[MemoryService] Redis client not available for push_data_result_ref")
            return
        current = [ChatBIResultRef.from_dict(item) for item in await self.get_data_result_stack(user_id, conversation_id)]
        stack = push_result_ref(current, ChatBIResultRef.from_dict(payload), max_depth=max_depth)
        key = self._get_data_result_stack_key(user_id, conversation_id)
        try:
            await redis.set(
                key,
                json.dumps([item.to_dict() for item in stack], ensure_ascii=False),
                ex=self.ttl,
            )
        except Exception as e:
            logger.error("[MemoryService] Failed to push data result stack key %s: %s", key, e)

    async def get_current_data_result(
        self,
        user_id: str,
        conversation_id: str,
    ) -> Optional[Dict[str, Any]]:
        stack = await self.get_data_result_stack(user_id, conversation_id)
        if stack:
            return stack[-1]
        return await self.get_last_data_result(user_id, conversation_id)

    async def get_history(self, user_id: str, conversation_id: str, limit: Optional[int] = None, offset: int = 0) -> List[Dict[str, str]]:
        """
        Retrieve history from Redis with pagination support.
        offset=0 means the most recent messages.

        通过 `llen` 定位并仅拉取所需的窗口切片（反向分页）：
        取最近若干条（以及 max_history_len 保留窗口内）时，不再 lrange 全量拉到 Python 侧，
        而是直接在 Redis 端截取目标区间，减少大列表下的数据传输。
        """
        redis = await get_redis()
        if not redis:
            return []

        key = self._get_key(user_id, conversation_id)
        total = await redis.llen(key)
        logger.info(f"[MemoryService] Fetching history for key: {key}. Total items: {total}, Limit: {limit}, Offset: {offset}")

        # Max Retention Window: 只回看最近 max_history_len 条
        if total > self.max_history_len:
            valid_start = total - self.max_history_len
            valid_end = total
        else:
            valid_start = 0
            valid_end = total

        # 反向分页：end_exclusive 为保留窗口的尾部开区间上界，start_incl 为其下界。
        # 当 limit 大于可用条数时，窗口左边界会越过保留窗口起点：此时应向上钳制到
        # valid_start（返回窗口内全部可用条），而非返回空——与旧实现的 clamp 语义一致，
        # 避免 GET(limit=50) 在历史只有 2 条时读到空、导致真实 Redis 下 history 消失。
        if limit is not None and limit > 0:
            end_exclusive = valid_end - offset
            if end_exclusive <= valid_start:
                return []  # offset 已越过保留窗口，无可读条
            start_incl = max(end_exclusive - limit, valid_start)
            data = await redis.lrange(key, start_incl, end_exclusive - 1)
        else:
            data = await redis.lrange(key, valid_start, valid_end - 1)

        history = []
        for item in data:
            try:
                history.append(json.loads(item))
            except Exception as e:
                logger.error(f"Failed to parse history item: {item}. Error: {e}")

        return history

    async def add_message(self, user_id: str, conversation_id: str, role: str, content: str, trace_id: Optional[str] = None, files: Optional[List[Dict[str, Any]]] = None, agent_name: Optional[str] = None, agent_type: Optional[str] = None, agent_display_name: Optional[str] = None, prompt_tokens: Optional[int] = 0, completion_tokens: Optional[int] = 0, total_tokens: Optional[int] = None, has_data_output: Optional[bool] = None, reasoning_content: Optional[str] = None, process_timeline: Optional[List[Dict[str, Any]]] = None):
        """
        Append a single message to the conversation history.
        Now supports trace_id, attachment files, and token usage values.

        agent_name: 处理该轮的智能体 name(slug)。仅对 assistant 消息记录，
        用于后续路由的会话粘性（让追问沿用上一轮智能体）。
        agent_type: 处理该轮的智能体类型（如 system/agent/rag 等主类型）。仅对 assistant 消息记录。
        agent_display_name: 处理该轮的智能体展示名。仅对 assistant 消息记录。
        """
        redis = await get_redis()
        if not redis:
            logger.warning("[MemoryService] Redis client not available for add_message")
            return
            
        from datetime import datetime
        key = self._get_key(user_id, conversation_id)
        # 扩展消息体，包含 trace_id 和 files
        message = {
            "role": role, 
            "content": content,
            "trace_id": trace_id,
            "timestamp": datetime.now().isoformat()
        }
        if files:
            message["files"] = files
        if agent_name:
            message["agent_name"] = agent_name
        if role == "assistant":
            message["agent_type"] = agent_type or "GENERAL"
            if agent_display_name:
                message["agent_display_name"] = agent_display_name
        if reasoning_content:
            message["reasoning_content"] = reasoning_content
        if process_timeline:
            message["process_timeline"] = process_timeline
        _prompt_tokens = int(prompt_tokens or 0)
        _completion_tokens = int(completion_tokens or 0)
        message["prompt_tokens"] = _prompt_tokens
        message["completion_tokens"] = _completion_tokens
        message["total_tokens"] = int(total_tokens or (_prompt_tokens + _completion_tokens))
        message["has_data_output"] = bool(has_data_output or False)

        
        # Push to list
        try:
            val = json.dumps(message, ensure_ascii=False)
            async with redis.pipeline() as pipe:
                await pipe.rpush(key, val)
                await pipe.ltrim(key, -self.max_history_len, -1)
                await pipe.expire(key, self.ttl)
                await pipe.execute()
            logger.info(f"[MemoryService] Added message to key: {key}. TraceID: {trace_id}")
        except Exception as e:
            logger.error(f"[MemoryService] Failed to add message to key {key}: {e}")

    async def update_last_user_message_content(
        self,
        user_id: str,
        conversation_id: str,
        content: str,
    ) -> bool:
        """Patch the latest user message content (e.g. persist vision sidecar text)."""
        redis = await get_redis()
        if not redis:
            logger.warning("[MemoryService] Redis client not available for update_last_user_message_content")
            return False
        key = self._get_key(user_id, conversation_id)
        try:
            data = await redis.lrange(key, 0, -1)
            for index in range(len(data) - 1, -1, -1):
                try:
                    message = json.loads(data[index])
                except Exception:
                    continue
                if message.get("role") != "user":
                    continue
                message["content"] = content
                await redis.lset(key, index, json.dumps(message, ensure_ascii=False))
                return True
        except Exception as e:
            logger.error(f"[MemoryService] Failed to update last user message for key {key}: {e}")
            return False
        return False

    async def truncate_history(
        self,
        user_id: str,
        conversation_id: str,
        keep_count: int,
    ) -> bool:
        """
        Truncate conversation history to keep only the first `keep_count` messages.
        If keep_count <= 0, deletes the entire history key.
        """
        redis = await get_redis()
        if not redis:
            logger.warning("[MemoryService] Redis client not available for truncate_history")
            return False
        key = self._get_key(user_id, conversation_id)
        try:
            if keep_count <= 0:
                await redis.delete(key)
                logger.info(f"[MemoryService] Deleted history key: {key}")
            else:
                await redis.ltrim(key, 0, keep_count - 1)
                await redis.expire(key, self.ttl)
                logger.info(f"[MemoryService] Truncated history key: {key} to {keep_count} items")
            return True
        except Exception as e:
            logger.error(f"[MemoryService] Failed to truncate history for key {key}: {e}")
            return False

    async def get_last_data_result(self, user_id: str, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve the latest structured SQL result for follow-up analysis/chart requests.
        """
        redis = await get_redis()
        if not redis:
            return None

        key = self._get_data_result_key(user_id, conversation_id)
        try:
            raw = await redis.get(key)
            if not raw:
                return None
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else None
        except Exception as e:
            logger.error(f"[MemoryService] Failed to get last data result from key {key}: {e}")
            return None

    async def set_last_data_result(self, user_id: str, conversation_id: str, payload: Dict[str, Any]):
        """
        Store the latest structured SQL result so follow-up turns can reuse it without re-querying.
        """
        redis = await get_redis()
        if not redis:
            logger.warning("[MemoryService] Redis client not available for set_last_data_result")
            return

        key = self._get_data_result_key(user_id, conversation_id)
        try:
            await redis.set(key, json.dumps(payload, ensure_ascii=False), ex=self.ttl)
            logger.info(f"[MemoryService] Stored last data result for key: {key}")
        except Exception as e:
            logger.error(f"[MemoryService] Failed to set last data result for key {key}: {e}")

    async def get_session_tool_artifact(
        self,
        user_id: str,
        conversation_id: str,
    ) -> Optional[Dict[str, Any]]:
        """通用智能体：上一轮主工具结果快照。"""
        redis = await get_redis()
        if not redis:
            return None
        key = self._get_session_tool_artifact_key(user_id, conversation_id)
        try:
            raw = await redis.get(key)
            if not raw:
                return None
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else None
        except Exception as e:
            logger.error("[MemoryService] Failed to get session tool artifact %s: %s", key, e)
            return None

    async def set_session_tool_artifact(
        self,
        user_id: str,
        conversation_id: str,
        payload: Dict[str, Any],
    ) -> None:
        redis = await get_redis()
        if not redis:
            logger.warning("[MemoryService] Redis unavailable for set_session_tool_artifact")
            return
        key = self._get_session_tool_artifact_key(user_id, conversation_id)
        try:
            await redis.set(key, json.dumps(payload, ensure_ascii=False), ex=self.ttl)
            logger.info("[MemoryService] Stored session tool artifact for key: %s", key)
        except Exception as e:
            logger.error("[MemoryService] Failed to set session tool artifact %s: %s", key, e)

    async def clear_history(self, user_id: str, conversation_id: str):
        """
        Delete a conversation history.
        """
        redis = await get_redis()
        if not redis:
            return
        from app.services.conversation_resource_service import ConversationResourceService
        await ConversationResourceService.delete(user_id, conversation_id)
        key = self._get_key(user_id, conversation_id)
        logger.info(f"[MemoryService] Clearing history for key: {key}")
        await redis.delete(key)
        await redis.delete(self._get_data_result_key(user_id, conversation_id))
        await redis.delete(self._get_data_result_stack_key(user_id, conversation_id))
        await redis.delete(self._get_session_tool_artifact_key(user_id, conversation_id))

    async def delete_session_memory(
        self,
        user_id: str,
        conversation_id: str,
        include_summary: bool = True,
        user_name: str | None = None,
        user_info: dict | None = None,
    ):
        """Delete LIST history and optionally summary index doc."""
        await self.clear_history(user_id, conversation_id)
        from app.services.ai.runtime.agentscope.state_store import agent_state_store
        from app.services.ai.runtime.agentscope.workspace import delete_workspace_for_session

        await agent_state_store.delete(user_id, conversation_id)
        await delete_workspace_for_session(
            user_id,
            conversation_id,
            user_name=user_name,
            user_info=user_info,
        )
        if include_summary:
            from app.services.ai.memory_index_service import MemoryIndexService
            await MemoryIndexService.delete_summary(str(user_id), conversation_id)

    async def history_exists(self, user_id: str, conversation_id: str) -> bool:
        redis = await get_redis()
        if not redis:
            return False
        return bool(await redis.exists(self._get_key(user_id, conversation_id)))

    def _get_active_conversation_key(
        self,
        user_id: str,
        instance_id: Optional[str] = None,
    ) -> str:
        uid = str(user_id) if user_id else "anonymous"
        normalized_instance_id = str(instance_id or "").strip()
        if not normalized_instance_id:
            return f"{self.KEY_PREFIX}:{uid}:active"
        encoded_instance_id = quote(normalized_instance_id, safe="")
        return f"{self.KEY_PREFIX}:{uid}:active:{encoded_instance_id}"

    async def get_active_conversation(
        self,
        user_id: str,
        instance_id: Optional[str] = None,
    ) -> Optional[str]:
        redis = await get_redis()
        if not redis:
            return None
        key = self._get_active_conversation_key(user_id, instance_id)
        try:
            val = await redis.get(key)
            if isinstance(val, bytes):
                return val.decode("utf-8")
            return val
        except Exception as e:
            logger.error(f"[MemoryService] Failed to get active conversation: {e}")
            return None

    async def set_active_conversation(
        self,
        user_id: str,
        conversation_id: str,
        instance_id: Optional[str] = None,
    ):
        redis = await get_redis()
        if not redis:
            return
        key = self._get_active_conversation_key(user_id, instance_id)
        try:
            await redis.set(key, conversation_id)
            logger.info(f"[MemoryService] Set active conversation for key {key} to {conversation_id}")
        except Exception as e:
            logger.error(f"[MemoryService] Failed to set active conversation: {e}")


memory_service = MemoryService()


class LongTermMemoryService:
    """
    Manages Long-Term Memory (LTM) in Redis.
    Uses Redis HASH to store user preferences, core facts, and profiles.
    Key pattern: nanzi:agent:ltm:{user_id}
    """
    
    KEY_PREFIX = "nanzi:agent:ltm"

    def _get_key(self, user_id: str) -> str:
        uid = str(user_id) if user_id else "anonymous"
        return f"{self.KEY_PREFIX}:{uid}"

    async def update_preference(self, user_id: str, key: str, value: str) -> bool:
        """
        Store or update a specific long-term preference/fact for a user.
        """
        redis = await get_redis()
        if not redis:
            logger.warning("[LTM] Redis client not available for update_preference")
            return False
            
        redis_key = self._get_key(user_id)
        try:
            await redis.hset(redis_key, key, value)
            logger.info(f"[LTM] Updated key '{key}' for user '{user_id}' in Redis.")
            return True
        except Exception as e:
            logger.error(f"[LTM] Failed to update preference for key {key}: {e}")
            return False

    async def fetch_memory(self, user_id: str) -> Dict[str, str]:
        """
        Retrieve all long-term preferences and facts for a user.
        """
        redis = await get_redis()
        if not redis:
            logger.warning("[LTM] Redis client not available for fetch_memory")
            return {}
            
        redis_key = self._get_key(user_id)
        try:
            data = await redis.hgetall(redis_key)
            if not data:
                return {}
            result = {}
            for k, v in data.items():
                k_str = k.decode("utf-8") if isinstance(k, bytes) else str(k)
                v_str = v.decode("utf-8") if isinstance(v, bytes) else str(v)
                result[k_str] = v_str
            return result
        except Exception as e:
            logger.error(f"[LTM] Failed to fetch memory for user {user_id}: {e}")
            return {}

    async def delete_preference(self, user_id: str, key: str) -> bool:
        """
        Delete a specific long-term preference/fact for a user.
        """
        redis = await get_redis()
        if not redis:
            logger.warning("[LTM] Redis client not available for delete_preference")
            return False

        redis_key = self._get_key(user_id)
        try:
            await redis.hdel(redis_key, key)
            logger.info(f"[LTM] Deleted key '{key}' for user '{user_id}' in Redis.")
            return True
        except Exception as e:
            logger.error(f"[LTM] Failed to delete preference for key {key}: {e}")
            return False


ltm_service = LongTermMemoryService()
