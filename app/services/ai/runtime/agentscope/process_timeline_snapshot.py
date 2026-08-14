"""Compact thinking-card snapshot from SSE chunks for history replay."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

DETAILS_MAX_CHARS = 2000


def _normalize_text(text: str, trim_boundary: bool = False) -> str:
    normalized = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    while "\n\n\n" in normalized:
        normalized = normalized.replace("\n\n\n", "\n\n")
    if trim_boundary:
        normalized = normalized.lstrip(" \t").lstrip("\n").rstrip(" \t").rstrip("\n")
    return normalized


def _append_text(existing: str, piece: str) -> str:
    combined = _normalize_text(f"{existing or ''}{piece or ''}")
    return combined if existing else combined.lstrip(" \t").lstrip("\n")


def _source_id(chunk: Dict[str, Any]) -> Optional[str]:
    name = str(chunk.get("agent_name") or "").strip()
    return name or None


def _last_pending_text(
    items: List[Dict[str, Any]],
    text_kind: str,
    source_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    for item in reversed(items):
        if item.get("kind") != "text" or item.get("textKind") != text_kind or not item.get("pending"):
            continue
        if source_id:
            if item.get("sourceId") == source_id:
                return item
            continue
        return item
    return None


def _find_log(items: List[Dict[str, Any]], log_id: Any) -> Optional[Dict[str, Any]]:
    for item in items:
        if item.get("kind") == "log" and item.get("id") == log_id:
            return item
        if item.get("kind") == "text":
            for child in item.get("children") or []:
                if child.get("id") == log_id:
                    return child
    return None


def _is_tool_log(data: Dict[str, Any]) -> bool:
    category = str(data.get("category") or "").lower()
    if category in {"permission", "external"}:
        return False
    if category in {"tool", "sql"}:
        return True
    if category:
        return False
    title = str(data.get("title") or "").lower()
    if any(token in title for token in ("权限", "permission", "确认", "外部执行")):
        return False
    return "工具" in title or "tool" in title


def _update_log(existing: Dict[str, Any], chunk: Dict[str, Any]) -> None:
    if chunk.get("title") is not None:
        existing["title"] = str(chunk.get("title") or existing.get("title") or "处理步骤")
    if "details" in chunk:
        existing["details"] = str(chunk.get("details") or "")
    if chunk.get("status") is not None:
        existing["status"] = str(chunk.get("status") or existing.get("status") or "success")
    if chunk.get("category") is not None:
        existing["category"] = chunk.get("category")
    if chunk.get("execution_time_ms") is not None:
        existing["execution_time_ms"] = chunk.get("execution_time_ms")


def _next_id(items: List[Dict[str, Any]], prefix: str) -> str:
    return f"{prefix}_{len(items) + 1}"


def _iter_logs(items: List[Dict[str, Any]]):
    for item in items:
        if item.get("kind") == "log":
            yield item
        elif item.get("kind") == "text":
            for child in item.get("children") or []:
                if child.get("kind") == "log":
                    yield child


def _last_pending_log(items: List[Dict[str, Any]], category: str) -> Optional[Dict[str, Any]]:
    found = None
    for log in _iter_logs(items):
        if log.get("status") == "pending" and log.get("category") == category:
            found = log
    return found


def _close_pending_logs(items: List[Dict[str, Any]], category: str) -> None:
    for log in _iter_logs(items):
        if log.get("status") == "pending" and log.get("category") == category:
            log["status"] = "success"


def _model_log_count(items: List[Dict[str, Any]]) -> int:
    return sum(1 for log in _iter_logs(items) if log.get("category") == "model")


def _format_duration_ms(duration_ms: Any) -> str:
    try:
        value = float(duration_ms or 0)
    except (TypeError, ValueError):
        value = 0.0
    return str(int(round(value)))


def apply_stream_chunk(state: List[Dict[str, Any]], chunk: Dict[str, Any]) -> None:
    """Mutate ``state`` with one user-visible thinking-card event."""
    if not isinstance(chunk, dict):
        return
    event_type = str(chunk.get("type") or "")
    source_id = _source_id(chunk)

    if event_type == "process_narration":
        piece = str(chunk.get("content") or "")
        if not piece.strip():
            return
        current = _last_pending_text(state, "narration", source_id)
        if current:
            current["content"] = _append_text(str(current.get("content") or ""), piece)
            return
        state.append({
            "kind": "text",
            "id": _next_id(state, "narration"),
            "textKind": "narration",
            "content": _append_text("", piece),
            "pending": True,
            "children": [],
            "sourceId": source_id,
            "sourceLabel": source_id,
        })
        return

    if event_type == "process_narration_commit":
        piece = _normalize_text(str(chunk.get("content") or ""), trim_boundary=True)
        current = _last_pending_text(state, "narration", source_id)
        if current:
            if piece:
                current["content"] = piece
            current["pending"] = False
            current.setdefault("children", [])
            return
        if piece:
            state.append({
                "kind": "text",
                "id": _next_id(state, "narration"),
                "textKind": "narration",
                "content": piece,
                "pending": False,
                "children": [],
                "sourceId": source_id,
                "sourceLabel": source_id,
            })
        return

    if event_type == "process_narration_promote":
        current = _last_pending_text(state, "narration", source_id)
        if current and current.get("pending"):
            state.remove(current)
        return

    if event_type == "model_call":
        phase = str(chunk.get("phase") or "")
        reply_id = str(chunk.get("reply_id") or "model")
        if phase == "start":
            _close_pending_logs(state, "model")
            seq = _model_log_count(state)
            apply_stream_chunk(state, {
                "type": "log",
                "id": f"model_call_{reply_id}_{seq}",
                "title": f"模型调用: {chunk.get('model_name') or 'unknown'}",
                "details": "等待模型响应...",
                "status": "pending",
                "category": "model",
            })
            return
        if phase == "end":
            pending = _last_pending_log(state, "model")
            model_name = str(chunk.get("model_name") or "").strip()
            input_tokens = int(chunk.get("input_tokens") or 0)
            output_tokens = int(chunk.get("output_tokens") or 0)
            duration_ms = chunk.get("duration_ms") or 0
            apply_stream_chunk(state, {
                "type": "log",
                "id": pending.get("id") if pending else f"model_call_{reply_id}_orphan",
                "title": (pending or {}).get("title") or (
                    f"模型调用: {model_name}" if model_name else "模型调用完成"
                ),
                "details": (
                    f"输入 {input_tokens} / 输出 {output_tokens} tokens，"
                    f"耗时 {_format_duration_ms(duration_ms)} ms"
                ),
                "status": "success",
                "category": "model",
                "execution_time_ms": duration_ms,
            })
        return

    if event_type == "router_log":
        thought = str(chunk.get("thought") or "No reasoning provided.")
        agent_name = str(chunk.get("selected_agent") or "Unknown")
        confidence = chunk.get("confidence")
        conf_text = f"（置信度: {confidence}）" if confidence is not None else ""
        apply_stream_chunk(state, {
            "type": "log",
            "id": _next_id(state, "router"),
            "title": "智能路由决策",
            "details": f"思考过程:\n{thought}\n\n最终选择: {agent_name} {conf_text}".rstrip(),
            "status": chunk.get("status") or "success",
            "category": "router",
            "execution_time_ms": chunk.get("execution_time_ms"),
        })
        return

    if event_type == "permission_result":
        apply_stream_chunk(state, {
            "type": "log",
            "id": f"permission_{chunk.get('permission_request_id') or _next_id(state, 'permission')}",
            "title": "已拒绝工具调用" if chunk.get("status") == "rejected" else "已允许工具调用",
            "details": f"确认请求: {chunk.get('permission_request_id') or ''}",
            "status": "success",
            "category": "permission",
        })
        return

    if event_type == "external_execution_result":
        apply_stream_chunk(state, {
            "type": "log",
            "id": f"external_result_{chunk.get('external_execution_request_id') or _next_id(state, 'external')}",
            "title": "外部执行失败" if chunk.get("status") == "error" else "外部执行结果已提交",
            "details": str(chunk.get("external_execution_request_id") or ""),
            "status": "error" if chunk.get("status") == "error" else "success",
            "category": "external",
        })
        return

    if event_type != "log":
        return

    log_id = chunk.get("id")
    if log_id is None:
        log_id = _next_id(state, "log")
    existing = _find_log(state, log_id)
    if existing:
        _update_log(existing, chunk)
        return

    log = {
        "kind": "log",
        "id": log_id,
        "title": str(chunk.get("title") or "处理步骤"),
        "details": str(chunk.get("details") or ""),
        "status": str(chunk.get("status") or "success"),
        "category": chunk.get("category"),
        "execution_time_ms": chunk.get("execution_time_ms"),
        "isExpanded": False,
    }
    parent = None
    if _is_tool_log(chunk):
        for item in reversed(state):
            if (
                item.get("kind") == "text"
                and item.get("textKind") == "narration"
                and not item.get("pending")
            ):
                parent = item
                break
    if parent is not None:
        parent.setdefault("children", []).append(log)
        return
    state.append(log)


def _truncate_details(text: Any) -> str:
    value = str(text or "")
    if len(value) <= DETAILS_MAX_CHARS:
        return value
    return value[: DETAILS_MAX_CHARS - 1] + "…"


def _finalize_log(item: Dict[str, Any]) -> Dict[str, Any]:
    copied = {
        "kind": "log",
        "id": item.get("id"),
        "title": str(item.get("title") or "处理步骤"),
        "details": _truncate_details(item.get("details")),
        "status": str(item.get("status") or "success"),
        "isExpanded": False,
    }
    if item.get("category") is not None:
        copied["category"] = item.get("category")
    if item.get("execution_time_ms") is not None:
        copied["execution_time_ms"] = item.get("execution_time_ms")
    return copied


def finalize_process_timeline(state: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
    """Drop pending body candidates and compact tool payloads for persistence."""
    items: List[Dict[str, Any]] = []
    for item in list(state or []):
        if item.get("kind") == "text" and item.get("textKind") == "narration" and item.get("pending"):
            continue
        if item.get("kind") == "log":
            copied = _finalize_log(item)
            if copied.get("status") == "pending" and copied.get("category") == "model":
                copied["status"] = "success"
            items.append(copied)
            continue
        if item.get("kind") != "text":
            continue
        copied: Dict[str, Any] = {
            "kind": "text",
            "id": item.get("id"),
            "textKind": item.get("textKind") or "narration",
            "content": str(item.get("content") or ""),
            "pending": False,
            "children": [_finalize_log(child) for child in (item.get("children") or [])],
        }
        if item.get("sourceId"):
            copied["sourceId"] = item.get("sourceId")
            copied["sourceLabel"] = item.get("sourceLabel") or item.get("sourceId")
        items.append(copied)
    return items or None
