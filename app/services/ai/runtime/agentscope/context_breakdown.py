"""AgentScope 模型请求的上下文组成估算。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Sequence

logger = logging.getLogger(__name__)


@dataclass
class ModelInputTokenMemo:
    """单次模型调用内复用完整输入 token 计数结果。"""

    total_tokens: int | None = None

    async def count_total(
        self,
        current_model: Any,
        messages: Sequence[Any],
        tools: Sequence[Any],
    ) -> int:
        if self.total_tokens is not None:
            return self.total_tokens
        counted = await current_model.count_tokens(
            messages=list(messages),
            tools=list(tools),
        )
        self.total_tokens = _safe_nonnegative_int(counted)
        return self.total_tokens


def empty_context_breakdown() -> dict[str, Any]:
    return {
        "system_prompt_tokens": 0,
        "tools_tokens": 0,
        "conversation_tokens": 0,
        "total_tokens": 0,
        "estimated": False,
        "source": "unavailable",
    }


def _safe_nonnegative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


async def estimate_context_breakdown(
    current_model: Any,
    messages: Sequence[Any] | None,
    tools: Sequence[Any] | None,
    *,
    token_memo: ModelInputTokenMemo | None = None,
) -> dict[str, Any]:
    """按 AgentScope ``count_tokens`` 口径拆分一次模型输入。

    AgentScope 的统一计数器同时接受消息和工具 schema。这里分别计算完整输入、
    system 消息和工具 schema，剩余部分归入对话消息，保证三项之和与完整输入估算一致。
    计数失败只影响观测字段，不应阻断实际模型请求。
    """
    if current_model is None:
        return empty_context_breakdown()

    normalized_messages = list(messages or [])
    normalized_tools = list(tools or [])
    token_memo = token_memo or ModelInputTokenMemo()
    try:
        total_tokens = await token_memo.count_total(
            current_model,
            normalized_messages,
            normalized_tools,
        )
        system_messages = [
            message
            for message in normalized_messages
            if getattr(message, "role", None) == "system"
        ]
        system_prompt_tokens = (
            _safe_nonnegative_int(
                await current_model.count_tokens(
                    messages=system_messages,
                    tools=[],
                )
            )
            if system_messages
            else 0
        )
        tools_tokens = (
            _safe_nonnegative_int(
                await current_model.count_tokens(
                    messages=[],
                    tools=normalized_tools,
                )
            )
            if normalized_tools
            else 0
        )
        conversation_tokens = max(
            0,
            total_tokens - system_prompt_tokens - tools_tokens,
        )
        return {
            "system_prompt_tokens": system_prompt_tokens,
            "tools_tokens": tools_tokens,
            "conversation_tokens": conversation_tokens,
            "total_tokens": total_tokens,
            "estimated": True,
            "source": "agentscope_count_tokens",
        }
    except Exception as exc:
        logger.warning(
            "[ContextBreakdown] Failed to estimate model input breakdown: %s",
            exc,
        )
        return empty_context_breakdown()
