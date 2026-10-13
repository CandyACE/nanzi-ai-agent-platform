"""禁用工具目录：内置高危工具候选（含运行时别名）的唯一来源。

设计口径见 docs/superpowers/specs/2026-10-13-forbidden-tool-catalog-design.md：
候选只覆盖执行与沙箱数据访问类工具，别名从 AGENTSCOPE_BUILTIN_TOOL_ALIASES
派生，保证目录与运行时拦截永远同源。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from app.services.ai.tools.registry import AGENTSCOPE_BUILTIN_TOOL_ALIASES


@dataclass(frozen=True)
class ForbiddenToolCandidate:
    """一个可禁用工具组；aliases 恒包含 id 自身，其余为运行时可命中的等价名。"""

    id: str
    label: str
    description: str
    category: str
    aliases: tuple[str, ...]
    group_key: str
    group: str


# ── v2 分组字段 ──────────────────────────────────────────────────────────────
# 分组归属与展示文案由后端决定（设计 §3.1）：前端只按 group_key 聚合、直接渲染
# group。让前端拼标签会再造一份与 category 平行的硬编码，v1 已经吃过三份硬编码
# 各自漂移的亏。
BUILTIN_CATEGORY_GROUP_LABELS: dict[str, str] = {
    "sandbox": "沙箱命令",
    "file": "文件操作",
    "process": "进程管理",
    "knowledge": "知识库",
}
BUILTIN_GROUP_LABEL_FALLBACK = "其他内置工具"
API_GROUP_PREFIX = "自定义 API"
API_UNGROUPED_GROUP_KEY = "api:__ungrouped__"
API_UNGROUPED_LABEL = "未分组"
MCP_GROUP_PREFIX = "MCP"
MCP_UNKNOWN_GROUP_KEY = "mcp:__unknown__"
MCP_UNKNOWN_LABEL = "未知服务"


def builtin_group(category: Any) -> tuple[str, str]:
    """内置候选的 (group_key, group)：按 category 归组，未知类别落到兜底标签。"""
    normalized = str(category or "").strip()
    label = BUILTIN_CATEGORY_GROUP_LABELS.get(
        normalized, BUILTIN_GROUP_LABEL_FALLBACK
    )
    return f"builtin:{normalized or 'other'}", label


def api_tool_group(group_name: Any) -> tuple[str, str]:
    """自定义 API 工具的 (group_key, group)：业务分组为空时归入「未分组」。"""
    normalized = str(group_name or "").strip()
    if not normalized:
        return (
            API_UNGROUPED_GROUP_KEY,
            f"{API_GROUP_PREFIX} · {API_UNGROUPED_LABEL}",
        )
    return f"api:{normalized}", f"{API_GROUP_PREFIX} · {normalized}"


def mcp_tool_group(server_name: Any) -> tuple[str, str]:
    """MCP 工具的 (group_key, group)：服务名缺失时归入「未知服务」。"""
    normalized = str(server_name or "").strip()
    if not normalized:
        return MCP_UNKNOWN_GROUP_KEY, f"{MCP_GROUP_PREFIX} · {MCP_UNKNOWN_LABEL}"
    return f"mcp:{normalized}", f"{MCP_GROUP_PREFIX} · {normalized}"


# (规范 id, 中文名, 描述, 分类, 运行时别名组 target 或 None)
_BUILTIN_FORBIDDEN_TOOL_SPECS: tuple[tuple[str, str, str, str, str | None], ...] = (
    (
        "exec_command",
        "执行终端命令 (exec_command)",
        "在沙箱中执行 Bash/shell 命令行",
        "sandbox",
        "Bash",
    ),
    (
        "write_file",
        "写入/修改文件 (write_file)",
        "对沙箱目录物理写入或修改代码文件",
        "file",
        "Write",
    ),
    (
        "edit_file",
        "编辑文件内容 (edit_file)",
        "在沙箱文件中做精确字符串替换，要求先读取目标文件",
        "file",
        "Edit",
    ),
    (
        "read_file",
        "读取文件内容 (read_file)",
        "读取沙箱工作目录中的文本或源代码",
        "file",
        "Read",
    ),
    (
        "search_text",
        "检索文件内容 (search_text)",
        "基于 ripgrep 搜索沙箱文件内容",
        "file",
        "Grep",
    ),
    (
        "glob_files",
        "查找文件 (glob_files)",
        "按 glob 模式查找沙箱中的文件",
        "file",
        "Glob",
    ),
    (
        "manage_process",
        "进程管理 (manage_process)",
        "查看或终止沙箱中的系统进程",
        "process",
        None,
    ),
    (
        "list_process",
        "查看系统进程 (list_process)",
        "列出当前系统进程及 CPU、内存占用",
        "process",
        None,
    ),
    (
        "search_qa_examples",
        "检索经验库 (search_qa_examples)",
        "检索历史问答优质案例及 SQL",
        "knowledge",
        None,
    ),
)


def _aliases_for(spec_id: str, alias_target: str | None) -> tuple[str, ...]:
    """规范 id 恒排首位，其余同组别名按字母序，保证输出稳定可测。"""
    if alias_target is None:
        return (spec_id,)
    members = {
        spec_id,
        alias_target,
        *(alias for alias, target in AGENTSCOPE_BUILTIN_TOOL_ALIASES.items() if target == alias_target),
    }
    return tuple(sorted(members, key=lambda name: (name != spec_id, name)))


def _builtin_candidate(
    spec: tuple[str, str, str, str, str | None],
) -> ForbiddenToolCandidate:
    spec_id, label, description, category, alias_target = spec
    group_key, group = builtin_group(category)
    return ForbiddenToolCandidate(
        id=spec_id,
        label=label,
        description=description,
        category=category,
        aliases=_aliases_for(spec_id, alias_target),
        group_key=group_key,
        group=group,
    )


BUILTIN_FORBIDDEN_TOOL_CANDIDATES: tuple[ForbiddenToolCandidate, ...] = tuple(
    _builtin_candidate(spec) for spec in _BUILTIN_FORBIDDEN_TOOL_SPECS
)


def merge_forbidden_tool_candidates(
    builtin: Iterable[ForbiddenToolCandidate],
    dynamic: Iterable[ForbiddenToolCandidate],
) -> list[ForbiddenToolCandidate]:
    """内置优先合并：内置候选恒排在前，同 id（忽略大小写）时保留内置项。"""
    merged: list[ForbiddenToolCandidate] = []
    seen: set[str] = set()
    for candidate in (*builtin, *dynamic):
        key = str(candidate.id).strip().casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(candidate)
    return merged
