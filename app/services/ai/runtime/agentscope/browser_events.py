from __future__ import annotations

import json
from typing import Any


def build_browser_session_event(tool_name: str, output: Any) -> dict[str, Any] | None:
    """把 browser_open 工具结果转换为不携带 viewer token 的面板事件。"""
    if str(tool_name or "") != "browser_open":
        return None
    raw = output.get("text") if isinstance(output, dict) else output
    try:
        payload = json.loads(str(raw or ""))
    except (TypeError, ValueError):
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
