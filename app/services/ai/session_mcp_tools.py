"""会话 resource_scope.mcp_tools 与智能体版本 tools 的并集注入。"""

from __future__ import annotations

from typing import Any, Iterable, List, Optional, Sequence


def _tool_config_name(item: Any) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        return str(item.get("name") or "").strip()
    return str(getattr(item, "name", "") or "").strip()


def extract_session_mcp_tool_names(resource_scope: Optional[dict[str, Any]]) -> List[str]:
    """从会话资源范围提取 MCP 工具名（保序去重）。"""
    names: List[str] = []
    seen: set[str] = set()
    for item in (resource_scope or {}).get("mcp_tools") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
    return names


def merge_tools_with_session_mcp(
    configured_tools: Sequence[Any] | None,
    resource_scope: Optional[dict[str, Any]],
) -> List[Any]:
    """
    版本 tools ∪ 会话 mcp_tools（按工具名去重）。

    已有配置项保留原形态（str / ToolConfigItem / dict）；
    会话新增工具以纯 name 字符串追加。
    """
    merged: List[Any] = list(configured_tools or [])
    seen = {_tool_config_name(item) for item in merged if _tool_config_name(item)}
    for name in extract_session_mcp_tool_names(resource_scope):
        if name in seen:
            continue
        merged.append(name)
        seen.add(name)
    return merged


def apply_session_mcp_tools_to_agent_config(
    agent_config: Any,
    resource_scope: Optional[dict[str, Any]],
) -> List[str]:
    """
    就地写回 agent_config.tools，返回本次新追加的 MCP 工具名。
    """
    before = {
        _tool_config_name(item)
        for item in (getattr(agent_config, "tools", None) or [])
        if _tool_config_name(item)
    }
    merged = merge_tools_with_session_mcp(
        getattr(agent_config, "tools", None),
        resource_scope,
    )
    agent_config.tools = merged
    after_added = [
        name
        for name in extract_session_mcp_tool_names(resource_scope)
        if name not in before
    ]
    return after_added
