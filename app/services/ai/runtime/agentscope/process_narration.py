"""Classify native model text without interrupting the visible stream."""
from __future__ import annotations

import re
from typing import Any, Dict, List


def _pending_text(state: Dict[str, Any]) -> str:
    return str(state.get("pending_reply_text") or "")


def _has_visible_text(text: str) -> bool:
    return bool(str(text or "").translate({ord(char): None for char in "\u200b\u200c\u200d\ufeff"}).strip())


def _append_narration(state: Dict[str, Any], piece: str) -> None:
    existing = str(state.get("process_narration") or "")
    text = str(piece or "")
    if not text:
        return
    if existing and not existing.endswith("\n"):
        existing += "\n\n"
    state["process_narration"] = existing + text


def _commit_pending_as_narration(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    pending = _pending_text(state)
    if not pending:
        return []
    events: List[Dict[str, Any]] = []
    if not state.get("pending_reply_emitted"):
        events.append({"type": "process_narration", "content": pending})
    _append_narration(state, pending)
    state["pending_reply_text"] = ""
    state["pending_reply_emitted"] = False
    events.append({"type": "process_narration_commit", "content": pending})
    return events


def _get_repetition_detector(state: Dict[str, Any]):
    detector = state.get("repetition_detector")
    if detector is None:
        from app.services.ai.runtime.stream_repetition_detector import StreamRepetitionDetector

        detector = StreamRepetitionDetector()
        state["repetition_detector"] = detector
    return detector


def on_model_call_start(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Start a model turn and flush only an unfinished prior candidate."""
    events = on_model_call_end(state)
    state["pending_reply_text"] = ""
    state["pending_reply_emitted"] = False
    state["current_reply_used_tools"] = False
    detector = state.get("repetition_detector")
    if detector is not None:
        detector.reset()
    if state.get("used_tools"):
        state["reply_phase"] = "after_tool_candidate"
    return events


def on_text_delta(state: Dict[str, Any], delta: str) -> List[Dict[str, Any]]:
    text = str(delta or "")
    if not text:
        return []

    detector = _get_repetition_detector(state)
    if detector.is_fused:
        # 已熔断，直接丢弃后续文本增量，彻底防止刷屏与内存累积
        return []

    verdict = detector.feed(text)
    if verdict.fused:
        state["repetition_fused"] = True
        error_msg = (
            f"\n\n⚠️ [流式安全拦截] {verdict.message}"
            "建议重新发起提问或切换更稳定的旗舰模型（如 DeepSeek-Chat / Claude）。"
        )
        return [{"type": "error", "status": "error", "content": error_msg}]

    pending = _pending_text(state)
    if not _has_visible_text(text) and not pending:
        return []

    state["pending_reply_text"] = pending + text
    state["pending_reply_emitted"] = True
    return [{"type": "process_narration", "content": text}]


def on_tool_call_start(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    state["used_tools"] = True
    state["current_reply_used_tools"] = True
    state["reply_phase"] = "tool_running"
    detector = state.get("repetition_detector")
    if detector is not None:
        detector.reset()
    return _commit_pending_as_narration(state)


def on_tool_result_end(state: Dict[str, Any]) -> None:
    """After a tool result, the next model text is still a candidate.

    It may introduce another tool call, so it must not become confirmed
    full_content until the current model call ends without starting another tool.
    """
    state["current_reply_used_tools"] = False
    state["reply_phase"] = "after_tool_candidate"


def on_model_call_end(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    pending = _pending_text(state)
    if not pending:
        return []
    if state.get("current_reply_used_tools"):
        return _commit_pending_as_narration(state)

    # No tool appeared in this model turn. The candidate was shown as
    # narration while we waited to see whether a tool call would follow;
    # promote it into the answer without sending the text a second time.
    state["pending_reply_text"] = ""
    state["pending_reply_emitted"] = False
    state["full_content"] = str(state.get("full_content") or "") + pending
    state["content_emitted"] = True
    return [{"type": "process_narration_promote", "content": pending}]


def agent_text_is_process_narration(state: Dict[str, Any], agent_text: str) -> bool:
    """AgentState 最近一条 assistant 文本若已作为过程说明发出，则不要再当正文补发。"""
    return not extract_agent_answer_after_process_narration(state, agent_text).strip()


def accumulate_visible_answer(full: str, chunk: Dict[str, Any]) -> str:
    """Merge a stream chunk into the confirmed/speculative visible answer."""
    chunk_type = str(chunk.get("type") or "")
    if chunk_type == "retraction":
        return str(chunk.get("content") or "")
    if chunk_type in {"process_narration_promote", "answer_delta", "error", "external_execution_required"}:
        return full + str(chunk.get("content") or "")
    if chunk_type:
        return full
    if "content" in chunk:
        return full + str(chunk["content"])
    return full


def extract_agent_answer_after_process_narration(state: Dict[str, Any], agent_text: str) -> str:
    """从 AgentState 文本中去掉已经展示过的过程话术前缀。

    某些适配器会把“我先查询一下……”和最终正文放在同一个 assistant
    文本块里。只用布尔值判断会在 reconcile 时把整段文本再次补发，造成
    过程话术和正文重复；这里保留未展示的正文尾部。

    AgentState 的多个 TEXT_BLOCK 以无分隔符拼接（``extract_latest_assistant_text``
    用 ``"".join``），而旁白块之间以 ``\n\n`` 连接；因此按空白序列通配匹配
    前缀，避免多块旁白因分隔符不一致而剥离失败、被整段补发为正文。
    """
    agent_raw = (agent_text or "").strip()
    if not agent_raw:
        return ""
    narration = str(state.get("process_narration") or "")
    narration += str(state.get("pending_reply_text") or "")
    narration = narration.strip()
    if not narration:
        return agent_raw
    if agent_raw == narration:
        return ""
    if agent_raw.startswith(narration):
        return agent_raw[len(narration):].lstrip()
    return _strip_narration_prefix_whitespace_wildcard(agent_raw, narration)


def _strip_narration_prefix_whitespace_wildcard(agent_raw: str, narration: str) -> str:
    """按“空白序列通配”剥离旁白前缀；剥离失败时原样返回。

    旁白块间空白（``\n\n``）在 AgentState 无分隔拼接中可能对应零个空白，
    所以把旁白按空白切分后以 ``\\s*`` 连接成正则，从头匹配原文前缀。
    """
    tokens = re.split(r"\s+", narration.strip())
    if not tokens or not tokens[0]:
        return agent_raw
    pattern = r"\s*".join(re.escape(token) for token in tokens)
    match = re.match(pattern, agent_raw)
    if not match:
        return agent_raw
    if match.end() >= len(agent_raw):
        return ""
    return agent_raw[match.end():].lstrip()
