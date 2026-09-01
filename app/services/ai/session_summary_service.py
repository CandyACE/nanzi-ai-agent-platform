"""Orchestrates session summary merge after chat turns."""
import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

from app.core.redis import get_redis
from app.services.ai.conversation_summarizer import ConversationSummarizer
from app.services.ai.daily_summary_service import DailySummaryService
from app.services.ai.embedding_client import EmbeddingClient
from app.services.ai.memory_index_service import MemoryIndexService, _doc_key
from app.services.ai.memory_service import memory_service
from app.services.memory_config_service import MemoryConfigService

logger = logging.getLogger(__name__)

DEBOUNCE_KEY_PREFIX = "memory:debounce:"
_SUMMARY_LOCKS: Dict[tuple[str, str], tuple[asyncio.AbstractEventLoop, asyncio.Lock]] = {}


class SessionSummaryService:
    @staticmethod
    def _summary_lock(user_id: str, conversation_id: str) -> asyncio.Lock:
        loop = asyncio.get_running_loop()
        key = (str(user_id), str(conversation_id))
        current = _SUMMARY_LOCKS.get(key)
        if current is None or current[0] is not loop:
            lock = asyncio.Lock()
            _SUMMARY_LOCKS[key] = (loop, lock)
            return lock
        return current[1]

    @staticmethod
    async def _snapshot_is_current(
        redis: Any,
        user_id: str,
        conversation_id: str,
        *,
        source_seq: int,
        source_revision: int,
    ) -> bool:
        """Reject a summary snapshot invalidated by a newer message or branch."""
        if not redis:
            return True
        try:
            seq_key = memory_service._get_seq_counter_key(user_id, conversation_id)
            revision_key = memory_service._get_context_revision_key(
                user_id, conversation_id
            )
            current_seq = int(await redis.get(seq_key) or 0)
            current_revision = int(await redis.get(revision_key) or 0)
        except (TypeError, ValueError):
            # Lightweight test doubles and legacy Redis values may not expose
            # these keys; the in-process lock still protects those callers.
            return True
        except Exception as exc:
            logger.warning("[SessionSummary] Snapshot check failed: %s", exc)
            return False
        return current_seq <= int(source_seq) and current_revision == int(source_revision)

    @staticmethod
    def _embedding_text(meta: Dict[str, Any]) -> str:
        parts = [
            meta.get("title") or "",
            meta.get("summary") or "",
            " ".join(str(v) for v in meta.get("key_facts") or []),
            " ".join(str(v) for v in meta.get("decisions") or []),
            " ".join(str(v) for v in meta.get("open_items") or []),
            " ".join(str(v) for v in meta.get("entities") or []),
            str(meta.get("memory_type") or ""),
        ]
        return "\n".join(p for p in parts if p)

    @staticmethod
    async def is_enabled() -> bool:
        if not await MemoryConfigService.get_bool("memory_service_enabled", True):
            return False
        return await MemoryConfigService.get_bool("memory_summary_enabled", True)

    @staticmethod
    def _debounce_key(user_id: str, conversation_id: str) -> str:
        return f"{DEBOUNCE_KEY_PREFIX}{user_id}:{conversation_id}"

    @staticmethod
    def _default_debounce_state() -> Dict[str, Any]:
        return {
            "last_run": 0,
            "pending_turns": 0,
            "synced_len": 0,
            "synced_seq": 0,
        }

    @staticmethod
    async def _load_debounce_state(
        redis: Any, user_id: str, conversation_id: str
    ) -> Dict[str, Any]:
        """Read current debounce state (last_run/pending_turns/synced_len/synced_seq),
        tolerating legacy states that predate the synced_len / synced_seq fields."""
        key = SessionSummaryService._debounce_key(user_id, conversation_id)
        raw = await redis.get(key)
        state = SessionSummaryService._default_debounce_state()
        if raw:
            try:
                loaded = json.loads(raw)
                if isinstance(loaded, dict):
                    state.update(
                        {
                            k: loaded.get(k, v)
                            for k, v in state.items()
                        }
                    )
            except (json.JSONDecodeError, TypeError):
                pass
        state["last_run"] = float(state.get("last_run") or 0)
        state["pending_turns"] = int(state.get("pending_turns") or 0)
        state["synced_len"] = int(state.get("synced_len") or 0)
        state["synced_seq"] = int(state.get("synced_seq") or 0)
        return state

    @staticmethod
    async def should_run(user_id: str, conversation_id: str, assistant_content: str) -> bool:
        min_chars = await MemoryConfigService.get_int("memory_summarize_min_assistant_chars", 30)
        if len((assistant_content or "").strip()) < min_chars:
            return False

        redis = await get_redis()
        if not redis:
            return True

        debounce_seconds = await MemoryConfigService.get_int("memory_summarize_debounce_seconds", 300)
        debounce_turns = await MemoryConfigService.get_int("memory_summarize_debounce_turns", 3)

        state = await SessionSummaryService._load_debounce_state(redis, user_id, conversation_id)
        key = SessionSummaryService._debounce_key(user_id, conversation_id)

        state["pending_turns"] = int(state.get("pending_turns", 0)) + 1
        now = time.time()
        last_run = float(state.get("last_run") or 0)

        if state["pending_turns"] < debounce_turns and (now - last_run) < debounce_seconds:
            await redis.set(key, json.dumps(state), ex=debounce_seconds * 2)
            return False

        state["last_run"] = now
        state["pending_turns"] = 0
        await redis.set(key, json.dumps(state), ex=debounce_seconds * 2)
        return True

    @staticmethod
    async def finalize_session(user_id: str, conversation_id: str) -> Dict[str, Any]:
        """Force summary flush when switching or closing a conversation (bypass debounce)."""
        if not await SessionSummaryService.is_enabled():
            return {"finalized": False, "reason": "service_disabled"}

        uid = str(user_id)
        cid = (conversation_id or "").strip()
        if not cid:
            return {"finalized": False, "reason": "missing_conversation_id"}

        history = await memory_service.get_history(uid, cid, limit=40)
        if not history:
            return {"finalized": False, "reason": "empty_history"}

        await SessionSummaryService.merge_session_summary(
            uid, cid, assistant_content=" ", force=True
        )
        return {"finalized": True, "conversation_id": cid}

    @staticmethod
    async def merge_session_summary(
        user_id: str,
        conversation_id: str,
        assistant_content: str = "",
        force: bool = False,
    ) -> None:
        if not await SessionSummaryService.is_enabled():
            return
        uid = str(user_id)
        cid = (conversation_id or "").strip()
        if not cid:
            return
        async with SessionSummaryService._summary_lock(uid, cid):
            if not force and not await SessionSummaryService.should_run(
                uid, cid, assistant_content
            ):
                return
            await SessionSummaryService._merge_session_summary_unlocked(
                uid, cid, assistant_content=assistant_content, force=force
            )

    @staticmethod
    async def _merge_session_summary_unlocked(
        user_id: str,
        conversation_id: str,
        assistant_content: str = "",
        force: bool = False,
    ) -> None:
        uid = str(user_id)
        cid = (conversation_id or "").strip()

        try:
            redis = await get_redis()
            snapshot_revision = 0
            if redis:
                try:
                    snapshot_revision = int(
                        await redis.get(
                            memory_service._get_context_revision_key(uid, cid)
                        )
                        or 0
                    )
                except (TypeError, ValueError):
                    snapshot_revision = 0
                except Exception as exc:
                    # Redis 客户端绑定事件循环；如果缓存连接暂时不可用，
                    # 跳过游标读取，最终仍由条件写入做并发保护。
                    logger.warning(
                        "[SessionSummary] Context revision unavailable; skip cache cursors: %s",
                        exc,
                    )
                    redis = None
            old_synced_len = 0
            old_synced_seq = 0
            debounce_state: Optional[Dict[str, Any]] = None
            debounce_key: Optional[str] = None
            if redis:
                debounce_state = await SessionSummaryService._load_debounce_state(
                    redis, uid, cid
                )
                debounce_key = SessionSummaryService._debounce_key(uid, cid)
                old_synced_len = debounce_state.get("synced_len", 0)
                old_synced_seq = debounce_state.get("synced_seq", 0)

            history = await memory_service.get_history(uid, cid, limit=None)
            if not history:
                # Nothing to summarise yet; still normalise both cursors so later
                # incremental merges start from a consistent snapshot.
                if redis and debounce_key and debounce_state:
                    debounce_state["synced_len"] = 0
                    debounce_state["synced_seq"] = 0
                    await redis.set(debounce_key, json.dumps(debounce_state), ex=600)
                return

            user_turn_count = len([m for m in history if m.get("role") == "user"])
            turn_count = max(1, user_turn_count)

            # Monotonic seq cursor. The Redis retention window keeps at most
            # `max_history_len` messages, so a positional `len(history)` cursor
            # permanently stalls once the window is full. Instead we advance on
            # the monotonic per-message `seq` (assigned by MemoryService) so the
            # incremental window keeps capturing new messages even when the list
            # length stays capped at 100.
            seqs = [m["seq"] for m in history if isinstance(m.get("seq"), int)]
            last_seq = max(seqs) if seqs else 0

            if not await SessionSummaryService._snapshot_is_current(
                redis,
                uid,
                cid,
                source_seq=last_seq,
                source_revision=snapshot_revision,
            ):
                logger.info(
                    "[SessionSummary] Skip stale snapshot before summarize user=%s conv=%s",
                    uid,
                    cid,
                )
                return

            prev = None
            if old_synced_seq > 0 and cid:
                prev = await SessionSummaryService._prev_summary(uid, cid)

            # Incremental window: messages that arrived since the previous
            # successful merge.
            incremental = None
            if seqs:
                # seq-based: every message carrying a seq above the synced cursor.
                above = [
                    m
                    for m in history
                    if isinstance(m.get("seq"), int) and m["seq"] > old_synced_seq
                ]
                if above:
                    incremental = above
            elif prev is not None and len(history) > old_synced_len:
                # Legacy fallback (pre-upgrade session whose messages carry no
                # seq yet): positional delta from the tail.
                incremental = history[old_synced_len:]

            if prev is not None and incremental is None:
                # No new messages since the last merge (the debounce already
                # consumed them, or force ran back-to-back). Reusing the
                # existing meta avoids a redundant LLM call and a redundant
                # embedding, while still refreshing recency.
                meta = SessionSummaryService._meta_from_prev(prev)
                changed = False
            else:
                if prev is None:
                    synthetic = history
                else:
                    synthetic = await SessionSummaryService._synthetic_incremental(
                        prev, incremental or history
                    )
                meta = await ConversationSummarizer.summarize(synthetic)
                changed = True

            title = meta.get("title") or "会话摘要"
            summary = meta.get("summary") or ""

            embedding = None
            re_embed = changed
            if changed and summary:
                # Skip re-embedding when the summarised content has not changed
                # materially since the stored snapshot (optimisation 2).
                if not SessionSummaryService._summary_substantially_changed(meta, prev):
                    re_embed = False
            if re_embed:
                try:
                    embed_text = SessionSummaryService._embedding_text(meta)
                    embedding = await EmbeddingClient.embed_text(embed_text)
                except Exception as e:
                    logger.warning("[SessionSummary] Embedding failed: %s", e)
            elif prev is not None and isinstance(prev, dict) and prev.get("has_embedding"):
                # A skipped re-embed means the semantic content is unchanged;
                # explicitly carry the old vector forward. `None` is reserved
                # for a real embedding failure and must clear stale vectors.
                embedding = prev.get("_embedding_vec")

            if not await SessionSummaryService._snapshot_is_current(
                redis,
                uid,
                cid,
                source_seq=last_seq,
                source_revision=snapshot_revision,
            ):
                logger.info(
                    "[SessionSummary] Skip stale snapshot before upsert user=%s conv=%s",
                    uid,
                    cid,
                )
                return

            summary_written = await MemoryIndexService.upsert_summary(
                user_id=uid,
                conversation_id=cid,
                title=title,
                summary=summary,
                turn_count=turn_count,
                embedding=embedding,
                key_facts=meta.get("key_facts") or [],
                decisions=meta.get("decisions") or [],
                open_items=meta.get("open_items") or [],
                entities=meta.get("entities") or [],
                memory_type=meta.get("memory_type") or "general",
                expected_seq=last_seq,
                expected_revision=snapshot_revision,
            )
            if summary_written is False:
                logger.info(
                    "[SessionSummary] Conditional summary write rejected user=%s conv=%s",
                    uid,
                    cid,
                )
                return
            if not await SessionSummaryService._snapshot_is_current(
                redis,
                uid,
                cid,
                source_seq=last_seq,
                source_revision=snapshot_revision,
            ):
                logger.info(
                    "[SessionSummary] Summary write became stale user=%s conv=%s",
                    uid,
                    cid,
                )
                return
            await DailySummaryService.refresh_for_date(uid)
            await SessionSummaryService._prune_excess_summaries(uid, keep_conversation_id=cid)

            # Record the synced seq cursor so the next merge consumes only the
            # newest delta. `synced_len` is kept as a legacy field for older
            # reads, but the seq cursor is authoritative.
            if redis and debounce_key and debounce_state:
                if not await SessionSummaryService._snapshot_is_current(
                    redis,
                    uid,
                    cid,
                    source_seq=last_seq,
                    source_revision=snapshot_revision,
                ):
                    return
                debounce_state["synced_len"] = len(history)
                debounce_state["synced_seq"] = last_seq
                await redis.set(debounce_key, json.dumps(debounce_state), ex=600)

            logger.info(
                "[SessionSummary] %s summary for user=%s conv=%s len=%d",
                "Updated" if changed else "Refreshed",
                uid,
                cid,
                len(history),
            )
        except Exception as e:
            logger.error("[SessionSummary] merge failed: %s", e, exc_info=True)

    @staticmethod
    async def _prev_summary(user_id: str, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Read the previously stored structured summary for a conversation,
        or None when none exists yet."""
        try:
            key = _doc_key(user_id, conversation_id)
            raw = await MemoryIndexService._hgetall_summary(key)
            if not raw:
                return None
            return await MemoryIndexService._parse_hash(raw)
        except Exception as e:
            logger.warning("[SessionSummary] read previous summary failed: %s", e)
            return None

    @staticmethod
    def _meta_from_prev(prev: Dict[str, Any]) -> Dict[str, Any]:
        """Rebuild a ConversationSummarizer-style meta dict from a stored hash
        (list-shaped fields were JSON-stringified on write)."""
        def _parse_list(value):
            if isinstance(value, list):
                return value
            if isinstance(value, str):
                try:
                    parsed = json.loads(value)
                    return parsed if isinstance(parsed, list) else []
                except (json.JSONDecodeError, TypeError):
                    return []
            return []

        return {
            "title": prev.get("title") or "",
            "summary": prev.get("summary") or "",
            "key_facts": _parse_list(prev.get("key_facts")),
            "decisions": _parse_list(prev.get("decisions")),
            "open_items": _parse_list(prev.get("open_items")),
            "entities": _parse_list(prev.get("entities")),
            "memory_type": prev.get("memory_type") or "general",
        }

    @staticmethod
    async def _synthetic_incremental(
        prev: Dict[str, Any], incremental: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Build a synthetic message list for an incremental re-summarise:
        one user turn carrying the existing summary, followed by the raw delta
        messages verbatim."""
        prev_text = json.dumps(
            {
                "title": prev.get("title") or "",
                "summary": prev.get("summary") or "",
                "key_facts": prev.get("key_facts") or [],
                "decisions": prev.get("decisions") or [],
                "open_items": prev.get("open_items") or [],
                "entities": prev.get("entities") or [],
                "memory_type": prev.get("memory_type") or "general",
            },
            ensure_ascii=False,
        )
        reminder = {
            "role": "user",
            "content": (
                "以下是该会话已有的结构化摘要。请在其基础上只增量更新"
                "（保留未变化的既有要点，合并与最新对话一致的内容，不要重复罗列已记录信息）：\n"
                f"{prev_text}"
            ),
        }
        return [reminder] + list(incremental)

    @staticmethod
    def _summary_substantially_changed(
        meta: Dict[str, Any], prev: Optional[Dict[str, Any]]
    ) -> bool:
        """Conservative change test for the summary payload: re-embed only when
        the title, summary body, or key facts materially moved."""
        if not prev:
            return True
        new_title = (meta.get("title") or "").strip()
        new_summary = (meta.get("summary") or "").strip()
        prev_title = (prev.get("title") or "").strip()
        prev_summary = (prev.get("summary") or "").strip()

        def facts(values) -> List[str]:
            return [str(f) for f in (values or [])]

        new_facts = facts(meta.get("key_facts"))
        prev_facts = facts(prev.get("key_facts"))

        if new_title == prev_title and len(new_summary) >= 12 and new_summary == prev_summary:
            return sorted(new_facts) != sorted(prev_facts)
        return True

    @staticmethod
    async def _prune_excess_summaries(user_id: str, *, keep_conversation_id: str = "") -> None:
        """Drop oldest session summaries beyond the configured max; tolerate legacy docs."""
        uid = str(user_id)
        keep_cid = str(keep_conversation_id or "").strip()
        max_sessions = await MemoryConfigService.get_int("memory_summary_max_sessions", 50)
        if max_sessions <= 0:
            return
        all_items = await MemoryIndexService.list_summaries(uid, limit=max_sessions + 10)
        if len(all_items) <= max_sessions:
            return
        for old in all_items[max_sessions:]:
            old_cid = str(old.get("conversation_id") or "").strip()
            if not old_cid:
                logger.warning(
                    "[SessionSummary] skip prune: missing conversation_id title=%s last_active=%s",
                    old.get("title"),
                    old.get("last_active"),
                )
                continue
            if keep_cid and old_cid == keep_cid:
                continue
            await MemoryIndexService.delete_summary(uid, old_cid)

    @staticmethod
    async def search_for_user(
        user_id: str,
        query: Optional[str] = None,
        scope: str = "summary",
        conversation_id: Optional[str] = None,
        limit: int = 5,
    ) -> Dict[str, Any]:
        uid = str(user_id)
        result: Dict[str, Any] = {"summaries": [], "history": []}

        query_embedding = None
        if query and query.strip():
            try:
                query_embedding = await EmbeddingClient.embed_text(query.strip())
            except Exception as e:
                logger.warning("[SessionSummary] query embed failed: %s", e)

        if scope in ("summary", "both"):
            result["summaries"] = await MemoryIndexService.search_summaries(
                uid, query=query, query_embedding=query_embedding, limit=limit
            )
            # Increment reference_count for each recalled summary
            redis = await get_redis()
            if redis and result["summaries"]:
                for s in result["summaries"]:
                    cid = s.get("conversation_id")
                    if cid:
                        key = f"memory:summary:{uid}:{cid}"
                        try:
                            # Increment reference_count in Redis
                            await redis.hincrby(key, "reference_count", 1)
                            # Update reference_count value in the current in-memory object
                            s["reference_count"] = int(s.get("reference_count") or 0) + 1
                        except Exception as ex:
                            logger.warning("[SessionSummary] failed to incr reference_count for key %s: %s", key, ex)

        if scope in ("history", "both"):
            cid = conversation_id
            if not cid and result["summaries"]:
                cid = result["summaries"][0].get("conversation_id")
            if cid:
                hist = await memory_service.get_history(uid, cid, limit=limit * 4)
                result["history"] = hist
                result["conversation_id"] = cid

        return result
