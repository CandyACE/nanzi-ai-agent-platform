"""命令禁用（``forbidden_commands``）的唯一策略来源。

监管的是"用户被禁止执行包含某个关键字的命令"这件事，而"执行命令"的入口有三个：
AgentScope 工具链（``tools.py``）、代码执行服务（``code_execution_service.py``）、
沙箱交互终端（``api/v1/endpoints/sandbox.py``）。三处各拼一套查询与匹配逻辑必然会漂移——
实际上首版就有两个漏：工具名只认 ``{exec_command, bash}``（沙箱 MCP 的 shell 叫
``mcp_sandbox_bash_<hash>``，这条路径完全不校验），终端接口一次都没查过。

因此这里收敛出两件事：
- ``is_shell_like_tool_name``：判定"这个工具是不是在执行 shell 命令"，替代两个硬编码名字；
- ``find_forbidden_command_rule`` / ``enforce_command_policy_for_http``：查询与匹配的唯一实现，
  分别供"需要 PermissionDecision 的工具链"和"需要 HTTP 异常的接口"使用。

降级方向与工具/命令侧既有约定一致：**查询失败 fail-closed**（由调用方转成 DENY / 5xx），
无身份与管理员放行（无身份只记日志，见 ``tools.py`` 的调用点）。
"""

from __future__ import annotations

import logging
import os
import shlex
from typing import Any, Iterable, Optional

logger = logging.getLogger(__name__)

# 精确名字：平台自有的、以及与"执行 shell"等价的工具名。
SHELL_TOOL_NAMES = frozenset(
    {
        "bash",
        "sh",
        "shell",
        "exec",
        "exec_command",
        "execute_command",
        "run_command",
        "command",
        "terminal",
    }
)

# MCP 工具名形态是 ``mcp_<可读名>_<hash>``（模型侧名字由 build_model_tool_name 生成）。
# 只按"含 shell 语义的词"放宽，而不是所有 mcp_* 都当 shell——否则 jira/postgres 这类
# 带 query 参数的 MCP 工具会被无谓地拉进命令匹配。
MCP_SHELL_MARKERS = ("bash", "shell", "exec")


class CommandPolicyUnavailable(RuntimeError):
    """权限策略查询失败。调用方必须 fail-closed，不能放行。"""


def is_shell_like_tool_name(tool_name: Any) -> bool:
    """该工具是否会执行一条 shell 命令（决定要不要过命令黑名单）。"""
    name = str(tool_name or "").strip().lower()
    if not name:
        return False
    if name in SHELL_TOOL_NAMES:
        return True
    if name.startswith("mcp_"):
        return any(marker in name for marker in MCP_SHELL_MARKERS)
    return False


def shell_command_tokens(command: str) -> list[str]:
    """把命令拆成"可执行名"序列：取 basename 并小写，丢掉纯分隔符。

    用 shlex 而不是 ``str.split``，是为了让 ``/bin/cat``、``cat;``、``a|cat`` 这类写法
    都归一到 ``cat``；``punctuation_chars`` 让 ``;&|()`` 单独成 token 后被过滤掉。
    """
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()")
        lexer.whitespace_split = True
        raw_tokens = list(lexer)
    except ValueError:
        raw_tokens = command.split()
    return [
        os.path.basename(token).lower()
        for token in raw_tokens
        if token and not all(char in ";&|()" for char in token)
    ]


def matches_forbidden_command(command: str, rule: str) -> bool:
    """命令是否命中某条禁用规则（按"连续 token 窗口"匹配）。

    逐 token 精确比对而不是子串包含：规则 ``rm`` 不该被 ``charm`` 命中，也不该拦下
    ``echo rm``（那只是把 rm 当参数打印）。规则本身可以是多词（``rm -rf``），
    因此在命令 token 序列上滑一个与规则等长的窗口。
    """
    command_tokens = shell_command_tokens(command)
    rule_tokens = shell_command_tokens(rule)
    if not rule_tokens or not command_tokens:
        return False
    window = len(rule_tokens)
    for start in range(len(command_tokens) - window + 1):
        if command_tokens[start : start + window] == rule_tokens:
            return True
    return False


async def find_forbidden_command_rule(
    user_id: Any,
    commands: Iterable[Any],
) -> Optional[str]:
    """返回命中的禁用规则关键字；没命中返回 ``None``。

    - 无身份（``None``/空）直接放行：本函数不做日志，调用方负责留痕（工具链那边已经有）；
    - 管理员放行；
    - 查询失败抛 ``CommandPolicyUnavailable``，由调用方转成 DENY / 5xx（fail-closed）。
    """
    if user_id is None or str(user_id).strip() == "":
        return None

    candidates = [str(cmd) for cmd in commands if cmd is not None and str(cmd).strip()]
    if not candidates:
        return None

    try:
        from app.core.orm import AsyncSessionLocal
        from app.services.permission_service import PermissionService

        async with AsyncSessionLocal() as session:
            perms = await PermissionService(session).get_user_permissions(int(user_id))
            if "admin" in (perms.roles or set()):
                return None
            rules = [
                str(rule).lower().strip()
                for rule in (getattr(perms.permissions, "forbidden_commands", None) or [])
                if str(rule).strip()
            ]
    except Exception as exc:  # noqa: BLE001 —— 统一转成可识别的失败信号
        raise CommandPolicyUnavailable(str(exc)) from exc

    if not rules:
        return None
    for command in candidates:
        for rule in rules:
            if matches_forbidden_command(command, rule):
                logger.warning(
                    "[forbidden] Command blacklist hit user=%s rule=%s command=%s",
                    user_id,
                    rule,
                    command[:200],
                )
                return rule
    return None


def command_forbidden_message(rule: str) -> str:
    """与工具链完全同源的用户可见文案，避免三个入口各写一套说法。"""
    return f"安全策略拦截：您的账号已被禁止在该智能体中执行包含 '{rule}' 的命令。"


async def enforce_command_policy_for_http(
    *,
    user_id: Any,
    commands: Iterable[Any],
) -> None:
    """HTTP 入口（沙箱交互终端）的命令校验：命中 403，策略不可用 503。

    放在端点里、真正下发执行之前，与 ``code_execution_service`` 口径一致——
    同一个"执行命令"动作不该因为走的是终端面板就绕过禁用。
    """
    from fastapi import HTTPException

    try:
        rule = await find_forbidden_command_rule(user_id, commands)
    except CommandPolicyUnavailable:
        logger.exception("[forbidden] Command policy unavailable for user=%s", user_id)
        raise HTTPException(
            status_code=503,
            detail="安全策略暂时无法验证，命令未执行，请稍后重试。",
        )
    if rule:
        raise HTTPException(status_code=403, detail=command_forbidden_message(rule))
