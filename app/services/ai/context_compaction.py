"""会话上下文压缩（compaction）。

当历史消息超过上下文窗口（``agent_max_context_messages``）时，旧消息原本会被直接丢弃，
导致多轮指代/事实断档。本模块用**确定性、零额外 LLM 调用**的方式，把被丢弃的旧消息
压缩成一段简短摘录，作为 system 消息注入到上下文最前面（由 ``normalize_messages_for_llm``
合并到系统区），在不增加延迟的前提下尽量保留对话连续性。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

COMPACTION_MARKER = "[早前对话摘录]"

# 摘录正文前的固定说明行前缀（从历史摘录里剥离，避免跨轮重复叠加污染正文）。
_PRELUDE_PREFIX = "以下是更早轮次对话的要点"

# 单条消息在摘录中的最大字符数，超过则截断。
_DEFAULT_PER_MESSAGE_CHARS = 120
# 整段摘录的最大字符数。
_DEFAULT_MAX_CHARS = 1200


def _extract_digest_body(content: Optional[str]) -> str:
    """从上一轮生成的完整摘录文本中剥离 marker 与说明行，仅保留要点正文。

    用于 B 项跨轮合并：把旧摘录当作更早的历史锚点，而不是把重复的 marker/说明
    再次叠加进新摘录。
    """
    if not content:
        return ""
    lines = (content or "").splitlines()
    keep: List[str] = []
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        if s == COMPACTION_MARKER or s.startswith(_PRELUDE_PREFIX):
            continue
        keep.append(ln)
    body = "\n".join(keep).strip()
    return body

_ROLE_LABELS = {
    "user": "用户",
    "assistant": "助手",
    "system": "系统",
}


def _flatten_content(content: Any) -> str:
    """将可能为多模态结构的 content 归一为纯文本。"""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text" and item.get("text"):
                    parts.append(str(item["text"]))
                elif item.get("type") == "image_url":
                    parts.append("[图片]")
            elif isinstance(item, str):
                parts.append(item)
        return " ".join(p for p in parts if p)
    return str(content)


def _condense(text: str, limit: int) -> str:
    collapsed = " ".join((text or "").split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: max(1, limit - 1)].rstrip() + "…"


def build_overflow_digest(
    dropped_messages: List[Dict[str, Any]],
    *,
    max_chars: int = _DEFAULT_MAX_CHARS,
    per_message_chars: int = _DEFAULT_PER_MESSAGE_CHARS,
    prev_digest: Optional[str] = None,
) -> Optional[Dict[str, str]]:
    """把被丢弃的旧消息压缩为一条 system 摘录消息。

    返回 ``{"role": "system", "content": ...}``；若无可用内容则返回 ``None``。
    纯文本拼接，不调用任何模型。最新的旧消息排在摘录末尾（更贴近当前上下文）。

    ``prev_digest``：上一轮持久化的摘录文本（B 项跨轮累积）。非空时，其要点正文
    作为「更早」的锚点叠加到新摘录最前；受 ``max_chars`` 整体限制，优先保留
    更贴近当前的新丢弃片段。
    """
    lines: List[str] = []
    for msg in dropped_messages or []:
        role = (msg.get("role") or "").strip()
        if role not in _ROLE_LABELS:
            continue
        text = _condense(_flatten_content(msg.get("content")), per_message_chars)
        # 工具结果（tool_run_text）同样会随 content 一起注入模型上下文（见
        # convert_history_to_messages），摘录也应收纳，否则工具返回的结论在压缩
        # 后会断档。工具结果单独截断、标签区分，避免挤占本人的文本配额。
        tool_text = _condense(
            _flatten_content(msg.get("tool_run_text")), per_message_chars
        )
        if tool_text:
            text = f"{text} · 工具结果：{tool_text}".strip(" ·") if text else tool_text
        if not text:
            continue
        lines.append(f"- {_ROLE_LABELS[role]}：{text}")

    # 更早的跨轮摘录作为背景行（保证最差也能保留一段），本轮新丢弃片段在其后。
    prev_items: List[str] = []
    if prev_digest:
        prev_body = _extract_digest_body(prev_digest)
        if prev_body:
            # 预截断到 max_chars 内，保证它是可选保留项而非必然被挤出或一直累积。
            prev_items.append(_condense(prev_body, max_chars))

    all_items = prev_items + lines
    if not all_items:
        return None

    # 从最新往回累加，保证保留的是离当前最近的旧消息；最终再恢复时间顺序。
    selected: List[str] = []
    used = 0
    for item in reversed(all_items):
        cost = len(item) + 1
        if selected and used + cost > max_chars:
            break
        selected.append(item)
        used += cost
    selected.reverse()

    if not selected:
        return None

    body = "\n".join(selected)
    content = (
        f"{COMPACTION_MARKER}\n"
        "以下是更早轮次对话的要点（已压缩，仅供理解上下文与指代，不要逐条复述）：\n"
        f"{body}"
    )
    return {"role": "system", "content": content}


def apply_context_compaction(
    *,
    full_history: List[Dict[str, Any]],
    window: List[Dict[str, Any]],
    max_chars: int = _DEFAULT_MAX_CHARS,
    prev_digest: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """在窗口前注入溢出摘录。

    ``full_history``：完整历史；``window``：截断后保留的窗口（不含本轮新消息）。
    若没有溢出（full_history 未超过 window）则原样返回 window。

    ``prev_digest``：上一轮持久化的摘录文本（B 项跨轮累积）。即使本轮无新溢出，
    也会把旧摘录作为锚点注入，保证早期历史不随窗口滑动而消失。
    """
    if not full_history or len(full_history) <= len(window):
        if prev_digest:
            return [{"role": "system", "content": prev_digest}] + window
        return window
    dropped = full_history[: len(full_history) - len(window)]
    digest = build_overflow_digest(
        dropped,
        max_chars=max_chars,
        prev_digest=prev_digest,
    )
    if not digest:
        return window
    return [digest] + window
