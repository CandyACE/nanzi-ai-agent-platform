"""Neutral tool metadata used by routing and tool-preflight observability."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class ToolMetadata:
    """Describe a tool without granting permission or changing invocation policy."""

    capability: str = "unknown"
    source: str = "unknown"
    freshness: str = "unknown"
    side_effect: str = "unknown"
    confirmation: str = "unknown"
    idempotent: str = "unknown"
    nudge_mode: str = "fallback"

    def to_dict(self) -> dict[str, str]:
        """Return JSON-safe metadata for logs and tests."""
        return {
            "capability": self.capability,
            "source": self.source,
            "freshness": self.freshness,
            "side_effect": self.side_effect,
            "confirmation": self.confirmation,
            "idempotent": self.idempotent,
            "nudge_mode": self.nudge_mode,
        }


_KNOWN_TOOL_METADATA: Mapping[str, ToolMetadata] = {
    "get_dataset_schema": ToolMetadata(
        capability="data_query",
        source="internal_structured_data",
        freshness="dynamic",
        side_effect="read",
        confirmation="none",
        idempotent="yes",
        nudge_mode="evidence",
    ),
    "execute_sql_query": ToolMetadata(
        capability="data_query",
        source="internal_structured_data",
        freshness="dynamic",
        side_effect="read",
        confirmation="policy",
        idempotent="no",
        nudge_mode="evidence",
    ),
    "search_knowledge_base": ToolMetadata(
        capability="knowledge_search",
        source="internal_docs",
        freshness="dynamic",
        side_effect="read",
        confirmation="none",
        idempotent="yes",
        nudge_mode="evidence",
    ),
    "sub_agent_call": ToolMetadata(
        capability="delegation",
        source="internal_agent",
        freshness="dynamic",
        side_effect="delegate",
        confirmation="inherited",
        idempotent="no",
        nudge_mode="explicit",
    ),
    "memory_search": ToolMetadata(
        capability="memory_search",
        source="conversation_context",
        freshness="historical",
        side_effect="read",
        confirmation="none",
        idempotent="yes",
        nudge_mode="special",
    ),
    "request_user_confirmation": ToolMetadata(
        capability="confirmation",
        source="platform_control",
        freshness="current_turn",
        side_effect="control",
        confirmation="ask",
        idempotent="yes",
        nudge_mode="explicit",
    ),
    "ask_user_question": ToolMetadata(
        capability="user_question",
        source="platform_control",
        freshness="current_turn",
        side_effect="control",
        confirmation="none",
        idempotent="no",
        nudge_mode="explicit",
    ),
    "Bash": ToolMetadata(
        capability="runtime_tool",
        source="runtime_environment",
        freshness="realtime",
        side_effect="unknown",
        confirmation="policy",
        idempotent="unknown",
        nudge_mode="fallback",
    ),
}


def resolve_tool_metadata(
    tool: Any,
    *,
    metadata_by_name: Mapping[str, ToolMetadata] | None = None,
) -> ToolMetadata:
    """Resolve explicit metadata and fall back to neutral values."""
    name = str(getattr(tool, "name", tool) or "").strip()
    if metadata_by_name and name in metadata_by_name:
        return metadata_by_name[name]
    if name in _KNOWN_TOOL_METADATA:
        return _KNOWN_TOOL_METADATA[name]

    permission_scope = str(getattr(tool, "permission_scope", "") or "").strip()
    source_type = str(getattr(tool, "source_type", "") or "").strip()
    if permission_scope or source_type:
        return ToolMetadata(
            source=source_type or "unknown",
            side_effect=("read" if permission_scope == "read" else "unknown"),
        )
    return ToolMetadata()


__all__ = ["ToolMetadata", "resolve_tool_metadata"]
