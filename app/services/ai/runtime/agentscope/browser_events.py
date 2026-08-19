from __future__ import annotations

import json
from typing import Any


def _browser_result_payload(output: Any) -> dict[str, Any] | None:
    raw = output.get("text") if isinstance(output, dict) else output
    try:
        payload = json.loads(str(raw or ""))
    except (TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def build_browser_session_event(tool_name: str, output: Any) -> dict[str, Any] | None:
    """把 browser_open 工具结果转换为不携带 viewer token 的面板事件。"""
    if str(tool_name or "") != "browser_open":
        return None
    payload = _browser_result_payload(output)
    if payload is None:
        return None
    session_id = str(payload.get("session_id") or "").strip()
    if not session_id:
        return None
    event = {
        "type": "browser_session",
        "session_id": session_id,
        "url": payload.get("url"),
        "title": payload.get("title"),
    }
    approval_mode = payload.get("approval_mode")
    if approval_mode in {"guarded", "autopilot"}:
        event["approval_mode"] = approval_mode
    return event


def build_browser_refresh_event(tool_name: str, output: Any) -> dict[str, Any] | None:
    """通知已连接的浏览器面板刷新 AI 操作后的页面，不透传工具结果。"""
    if str(tool_name or "") not in {"browser_click", "browser_fill"}:
        return None
    payload = _browser_result_payload(output)
    if payload is None:
        return None
    session_id = str(payload.get("session_id") or "").strip()
    if not session_id:
        return None
    return {"type": "browser_refresh", "session_id": session_id}
