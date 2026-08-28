"""AgentScope 工具结果状态与安全错误摘要。"""

from __future__ import annotations

import re
from typing import Any

from app.services.ai.error_response_service import sanitize_error_text


_FAILURE_STATES = frozenset({
    "error",
    "failed",
    "failure",
    "denied",
    "interrupted",
    "timeout",
    "timed_out",
})
_SUCCESS_STATES = frozenset({"success", "succeeded", "finished", "completed"})
_BASH_FAILURE_MARKER_RE = re.compile(
    r"(?im)^(?:command\s+(?:failed|timed out)|error\s*:|stderr\s*:|"
    r"permission denied\b|permissiondenied\b)"
)
_LEGACY_FAILURE_MARKER_RE = re.compile(
    r"(?i)(?:安全策略拦截|permission\s+denied|permissiondenied)"
)


def normalize_tool_result_state(value: Any) -> str:
    """将 AgentScope 枚举或兼容实现转换成稳定的小写状态名。"""

    raw = getattr(value, "value", value)
    return str(raw or "").strip().lower()


def _tool_output_text(output: Any) -> str:
    if isinstance(output, dict) and "text" in output:
        return str(output.get("text") or "")
    return str(output or "")


def is_tool_result_error(
    tool_name: str,
    output: Any,
    *,
    result_state: Any = None,
    domain_error: bool = False,
) -> bool:
    """判断工具是否失败，优先使用工具运行时的最终状态。

    AgentScope 的 ``ToolResultEndEvent.state`` 是执行结果的权威来源。
    文本标记只为旧事件或业务层错误保留兼容回退，避免成功输出中出现
    ``Error`` 单词时被误判。
    """

    if domain_error:
        return True

    state = normalize_tool_result_state(result_state)
    if state in _SUCCESS_STATES:
        return False
    if state in _FAILURE_STATES:
        return True

    text = _tool_output_text(output)
    if str(tool_name or "").strip().lower() == "bash":
        return bool(_BASH_FAILURE_MARKER_RE.search(text))
    return bool(_LEGACY_FAILURE_MARKER_RE.search(text))


def extract_tool_result_error_reason(
    tool_name: str,
    output: Any,
    *,
    result_state: Any = None,
    domain_error: bool = False,
    max_length: int = 300,
) -> str:
    """从失败结果提取一条脱敏摘要，供用户时间线展示。"""

    if not is_tool_result_error(
        tool_name,
        output,
        result_state=result_state,
        domain_error=domain_error,
    ):
        return ""

    text = _tool_output_text(output)
    lines = [line.strip() for line in text.splitlines()]
    non_empty = [line for line in lines if line]
    if not non_empty:
        return "工具执行失败"

    candidate = ""
    command_failed = False
    for index, line in enumerate(lines):
        lowered = line.lower()
        if lowered.startswith("command timed out"):
            candidate = "命令执行超时"
            break
        if lowered.startswith("command failed"):
            command_failed = True
        if lowered.startswith("stderr:"):
            remainder = line.split(":", 1)[1].strip()
            if remainder:
                candidate = remainder
                break
            candidate = next(
                (
                    next_line
                    for next_line in lines[index + 1 :]
                    if next_line and next_line.lower() not in {"stdout:", "stderr:"}
                ),
                "",
            )
            if candidate:
                break
        if lowered.startswith("error:"):
            candidate = line.split(":", 1)[1].strip() or line
            break

    if not candidate:
        if command_failed:
            candidate = "命令执行失败（退出码非 0）"
        else:
            candidate = next(
                (
                    line
                    for line in non_empty
                    if "timed out" in line.lower()
                    or line.lower().startswith("permission denied")
                    or line.lower().startswith("permissiondenied")
                ),
                non_empty[0],
            )

    return sanitize_error_text(candidate, max_length=max_length)
