"""Typed result protocol for sub-agent delegation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SubAgentResultStatus(str, Enum):
    """Lifecycle status exposed by a delegated execution."""

    COMPLETED = "completed"
    EMPTY = "empty"
    INTERRUPTED = "interrupted"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass(frozen=True)
class SubAgentRequest:
    """Normalized request metadata used by the delegation boundary."""

    target_agent_name: str
    query: str
    caller_agent_id: str | None = None
    caller_agent_name: str | None = None
    delegation_depth: int = 0
    approval_mode: str = "ask"
    capability: str | None = None
    authority: str = "inherited_permission"
    timeout_seconds: float | None = None
    background: bool = False

    def to_metadata(self) -> dict[str, Any]:
        """Return safe request metadata without user credentials or raw context."""
        return {
            "target_agent_name": self.target_agent_name,
            "query_chars": len(self.query),
            "caller_agent_id": self.caller_agent_id,
            "caller_agent_name": self.caller_agent_name,
            "delegation_depth": self.delegation_depth,
            "approval_mode": self.approval_mode,
            "capability": self.capability,
            "authority": self.authority,
            "timeout_seconds": self.timeout_seconds,
            "background": self.background,
        }


EMPTY_SUB_AGENT_RESULT_MESSAGE = (
    "子智能体已执行完成，但未产生可交付正文（可能仅有内部进度日志或工具中间结果）。"
    "请勿使用相同参数重复委派；请根据上述情况向用户说明，或建议其直接打开对应子智能体对话。"
)


@dataclass(frozen=True)
class SubAgentResult:
    """JSON-safe internal result that keeps delegation state separate from text."""

    status: SubAgentResultStatus
    target_agent_id: str | None = None
    target_agent_name: str | None = None
    content: str = ""
    error_code: str | None = None
    interrupt_type: str | None = None
    truncated: bool = False
    capability: str | None = None
    evidence: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)

    def to_tool_text(self) -> str:
        """Return the backward-compatible text presented to the calling model."""
        if self.content.strip():
            return self.content
        if self.status is SubAgentResultStatus.EMPTY:
            return EMPTY_SUB_AGENT_RESULT_MESSAGE
        return "错误：子智能体未产生可交付结果。"

    def to_metadata(self) -> dict[str, Any]:
        """Return non-sensitive metadata suitable for a trace or SSE meta event."""
        return {
            "status": self.status.value,
            "target_agent_id": self.target_agent_id,
            "target_agent_name": self.target_agent_name,
            "error_code": self.error_code,
            "interrupt_type": self.interrupt_type,
            "truncated": self.truncated,
            "capability": self.capability,
            "evidence_count": len(self.evidence),
            "artifact_count": len(self.artifacts),
            "content_chars": len(self.content),
        }


__all__ = [
    "EMPTY_SUB_AGENT_RESULT_MESSAGE",
    "SubAgentRequest",
    "SubAgentResult",
    "SubAgentResultStatus",
]
