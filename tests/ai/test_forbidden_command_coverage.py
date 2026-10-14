"""命令禁用（forbidden_commands）的覆盖面：工具名识别 + 所有执行入口。

首版有两个漏：
1. 名字 gate 只认 ``{exec_command, bash}``，而沙箱容器里的 shell 是 MCP 工具
   ``mcp_sandbox_bash_<hash>``（模型侧名字由 ``build_model_tool_name`` 生成）——该路径完全不校验；
2. 沙箱终端 HTTP 接口（``/sandbox/docker/workspace/exec``、``/sandbox/k8s/workspace/exec``，
   前端 Terminal 面板在用）直接调用运行时执行函数，一次都没查 ``forbidden_commands``。
   同一个「执行命令」动作，走 code_execution_service 有校验、走终端面板没有。

所以修法是两件事：命令策略收敛成单一来源（三个入口共用），且工具名判定从"两个硬编码名字"
改为"shell 类工具"识别。
"""

from __future__ import annotations

import inspect
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services.ai.runtime.command_policy import (
    matches_forbidden_command,
    shell_command_names,
)

pytestmark = pytest.mark.no_infrastructure


# ---------------------------------------------------------------- 工具名识别


@pytest.mark.parametrize(
    "tool_name",
    [
        "Bash",
        "bash",
        "exec_command",
        "shell",
        "run_command",
        "execute_command",
        "mcp_sandbox_bash_9f3a1c2b7e",  # 沙箱 MCP 的 shell（首版漏掉的就是它）
        "mcp_workspace_shell_1a2b3c4d5e",
        "mcp_container_exec_0f1e2d3c4b",
    ],
)
def test_shell_like_tool_names_are_recognized(tool_name):
    from app.services.ai.runtime.command_policy import is_shell_like_tool_name

    assert is_shell_like_tool_name(tool_name) is True, tool_name


@pytest.mark.parametrize(
    "tool_name",
    [
        "read_file",
        "write_file",
        "search_text",
        "search_qa_examples",
        "manage_process",
        "mcp_jira_search_9f3a1c2b7e",  # MCP 但非 shell：不能因为前缀就拦
        "mcp_postgres_query_1a2b3c4d5e",
        "BashOutput",  # 只读输出，不是执行入口
    ],
)
def test_non_shell_tools_are_not_matched(tool_name):
    from app.services.ai.runtime.command_policy import is_shell_like_tool_name

    assert is_shell_like_tool_name(tool_name) is False, tool_name


# ---------------------------------------------------------------- 策略查询单一来源


def _fake_permissions(forbidden_commands, roles=None, forbidden_tools=None):
    return SimpleNamespace(
        roles=roles or set(),
        permissions=SimpleNamespace(
            forbidden_commands=forbidden_commands,
            forbidden_tools=forbidden_tools or [],
        ),
    )


def _patch_permission_query(monkeypatch, perms):
    """把权限查询替换成受控实现，并统计调用次数。"""
    calls: list[int] = []

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return False

    class _Service:
        def __init__(self, _session):
            pass

        async def get_user_permissions(self, user_id, agent_id=None):
            calls.append(user_id)
            return perms

    monkeypatch.setattr("app.core.orm.AsyncSessionLocal", lambda: _Session())
    monkeypatch.setattr("app.services.permission_service.PermissionService", _Service)
    return calls


@pytest.mark.asyncio
async def test_hit_returns_the_matching_rule(monkeypatch):
    from app.services.ai.runtime.command_policy import find_forbidden_command_rule

    _patch_permission_query(monkeypatch, _fake_permissions(["cat", "shutdown"]))

    assert await find_forbidden_command_rule(7, ["cat /etc/passwd"]) == "cat"
    assert await find_forbidden_command_rule(7, ["echo hi"]) is None


@pytest.mark.asyncio
async def test_multiple_candidate_commands_are_all_checked(monkeypatch):
    """一个入口可能同时提交多段命令（例如终端接口的 script），任一段命中就要拦。"""
    from app.services.ai.runtime.command_policy import find_forbidden_command_rule

    _patch_permission_query(monkeypatch, _fake_permissions(["rm"]))

    assert await find_forbidden_command_rule(7, ["echo ok", "rm -rf /tmp/x"]) == "rm"
    assert await find_forbidden_command_rule(7, ["", None, "echo ok"]) is None


@pytest.mark.asyncio
async def test_admin_and_anonymous_are_exempt(monkeypatch):
    from app.services.ai.runtime.command_policy import find_forbidden_command_rule

    _patch_permission_query(monkeypatch, _fake_permissions(["cat"], roles={"admin"}))
    assert await find_forbidden_command_rule(7, ["cat /etc/passwd"]) is None

    # 无身份：沿用既有降级（放行），由调用方决定是否记日志
    assert await find_forbidden_command_rule(None, ["cat /etc/passwd"]) is None


@pytest.mark.asyncio
async def test_query_failure_is_fail_closed(monkeypatch):
    """查询失败必须能让调用方 fail-closed：与工具/命令侧的既有方向一致。"""
    from app.services.ai.runtime.command_policy import (
        CommandPolicyUnavailable,
        find_forbidden_command_rule,
    )

    class _Boom:
        def __init__(self, _session):
            pass

        async def get_user_permissions(self, _user_id, agent_id=None):
            raise RuntimeError("db down")

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return False

    monkeypatch.setattr("app.core.orm.AsyncSessionLocal", lambda: _Session())
    monkeypatch.setattr("app.services.permission_service.PermissionService", _Boom)

    with pytest.raises(CommandPolicyUnavailable):
        await find_forbidden_command_rule(7, ["cat /etc/passwd"])


# ---------------------------------------------------------------- 三个执行入口都接上


def test_tool_name_gate_no_longer_hardcodes_two_names():
    """源码级契约：不得再出现只认两个名字的判定。"""
    source = Path(
        "app/services/ai/runtime/agentscope/tools.py"
    ).read_text(encoding="utf-8")

    assert 'not in {"exec_command", "bash"}' not in source, "两个硬编码名字的 gate 必须去掉"
    assert "is_shell_like_tool_name" in source


def test_sandbox_terminal_endpoints_enforce_command_blacklist():
    """沙箱终端接口（前端 Terminal 面板）必须与 code_execution_service 同一口径。"""
    source = Path("app/api/v1/endpoints/sandbox.py").read_text(encoding="utf-8")

    assert source.count("enforce_command_policy_for_http(") == 2, (
        "docker 与 k8s 两个终端端点都要校验"
    )


def test_code_execution_service_reuses_the_shared_policy():
    """代码执行入口也不该自己拼一套查询逻辑。"""
    source = Path("app/services/ai/code_execution_service.py").read_text(encoding="utf-8")

    assert "find_forbidden_command_rule" in source


@pytest.mark.asyncio
async def test_mcp_sandbox_shell_is_now_blocked(monkeypatch):
    """端到端：模型侧拿到的是 mcp_*_bash_*，首版这会放行，现在必须 DENY。"""
    from agentscope.permission import PermissionBehavior

    from app.services.ai.runtime.agentscope import tools as tools_mod

    _patch_permission_query(monkeypatch, _fake_permissions(["cat"]))

    decision = await tools_mod.enforce_command_forbidden(
        "mcp_sandbox_bash_9f3a1c2b7e", {"command": "cat /etc/passwd"}, 7
    )

    assert decision is not None
    assert decision.behavior == PermissionBehavior.DENY
    assert decision.decision_reason == "hit_user_command_blacklist"


@pytest.mark.asyncio
async def test_http_helper_raises_403_with_the_same_message(monkeypatch):
    """HTTP 入口命中时给出可读的 403，而不是静默执行。"""
    from fastapi import HTTPException

    from app.services.ai.runtime.command_policy import enforce_command_policy_for_http

    _patch_permission_query(monkeypatch, _fake_permissions(["cat"]))

    with pytest.raises(HTTPException) as excinfo:
        await enforce_command_policy_for_http(user_id=7, commands=["cat /etc/passwd"])

    assert excinfo.value.status_code == 403
    assert "cat" in str(excinfo.value.detail)


@pytest.mark.asyncio
async def test_http_helper_passes_clean_commands(monkeypatch):
    from app.services.ai.runtime.command_policy import enforce_command_policy_for_http

    _patch_permission_query(monkeypatch, _fake_permissions(["cat"]))

    assert await enforce_command_policy_for_http(user_id=7, commands=["ls -al"]) is None


@pytest.mark.asyncio
async def test_http_helper_fails_closed_when_policy_is_unavailable(monkeypatch):
    """策略查不到时必须拒绝执行，而不是放行任意命令。"""
    from fastapi import HTTPException

    from app.services.ai.runtime.command_policy import enforce_command_policy_for_http

    class _Boom:
        def __init__(self, _session):
            pass

        async def get_user_permissions(self, _user_id, agent_id=None):
            raise RuntimeError("db down")

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return False

    monkeypatch.setattr("app.core.orm.AsyncSessionLocal", lambda: _Session())
    monkeypatch.setattr("app.services.permission_service.PermissionService", _Boom)

    with pytest.raises(HTTPException) as excinfo:
        await enforce_command_policy_for_http(user_id=7, commands=["cat /etc/passwd"])

    assert excinfo.value.status_code == 503


# ---------------------------------------------------------------------------
# 分词健壮性：包装器绕过、重定向粘连、参数误杀
#
# 背景（实测复现，见 ai review 核实）：旧实现对**每个** token 取 basename 后做窗口匹配，
# 于是 `sh -c "cat /etc/passwd"` 里的 `cat /etc/passwd` 是一个 token，basename 后变成
# `passwd` —— 禁用 `cat` 完全失效；`cat</etc/passwd` 同理只剩 `passwd`。
# 反向地，参数路径也被当命令名：`rm -rf /tmp/test` 会命中"禁用 test"。
# 正确语义是：只把**命令位置的 token** 当命令名，且包装器（sh -c / bash -c / env / sudo …）
# 要展开到内层真正执行的命令。
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        'sh -c "cat /etc/passwd"',
        "sh -c 'cat /etc/passwd'",
        'bash -c "cat /etc/passwd"',
        'bash -lc "cat /etc/passwd"',
        'env cat /etc/passwd',
        'sudo cat /etc/passwd',
        'nohup cat /etc/passwd',
        '/bin/sh -c "/bin/cat /etc/passwd"',
    ],
)
def test_wrapper_forms_do_not_bypass_a_banned_command(command):
    """包装器不能成为绕过通道——这正是 Agent 最常用的执行形态。"""
    assert matches_forbidden_command(command, "cat") is True, command


@pytest.mark.parametrize(
    "command",
    ["cat</etc/passwd", "cat</etc/passwd >/tmp/out", "cat /etc/passwd>/tmp/out"],
)
def test_redirection_does_not_swallow_the_command_name(command):
    """重定向符必须与命令名分开，否则 `cat` 会整个消失。"""
    assert matches_forbidden_command(command, "cat") is True, command


@pytest.mark.parametrize(
    "command",
    [
        "rm -rf /tmp/test",          # 参数路径 basename = test
        "cp /etc/test /tmp/x",       # 参数路径 basename = test
        "echo test",                 # 参数就是字符串
        "grep test /var/log/syslog",
    ],
)
def test_arguments_are_not_treated_as_command_names(command):
    """参数（含路径 basename）不是命令名：禁 `test` 不该拦下这些合法命令。"""
    assert matches_forbidden_command(command, "test") is False, command


def test_printing_a_banned_word_is_not_a_hit():
    """`echo rm` 只是把 rm 当字符串打印，docstring 明确说不该命中（旧实现与文档矛盾）。"""
    assert matches_forbidden_command("echo rm", "rm") is False
    assert matches_forbidden_command('sh -c "echo rm"', "rm") is False


def test_multi_word_rules_still_match_with_arguments():
    """多词规则（`rm -rf`）必须仍能匹配，不能被上面的收紧改坏。"""
    assert matches_forbidden_command("rm -rf /tmp/x", "rm -rf") is True
    assert matches_forbidden_command("rm -r /tmp/x", "rm -rf") is False
    assert matches_forbidden_command('sh -c "rm -rf /tmp/x"', "rm -rf") is True


def test_chained_commands_still_match_each_segment():
    """`;`/`&&`/`|` 串起来的每段都要判，不能只看第一段。"""
    assert matches_forbidden_command("echo hi; cat /etc/passwd", "cat") is True
    assert matches_forbidden_command("echo hi && cat /etc/passwd", "cat") is True
    assert matches_forbidden_command("echo hi | cat", "cat") is True
    assert matches_forbidden_command("cat /etc/passwd\nrm -rf /tmp/x", "rm") is True


# ---------------------------------------------------------------------------
# 重定向符与包装器参数：既不能误杀，更不能漏判
#
# 上一轮把 `<` `>` 当命令段分隔符，是为了修掉 `cat</etc/passwd` 连成一个 token
# （basename 后 `cat` 整个消失）。但它们**不是**命令分隔符——切段之后重定向目标
# 变成了新段的"命令名"，于是：
#   - 误杀：`echo hi > /tmp/rm` 会命中"禁用 rm"；
#   - 漏判（安全方向，更严重）：`sudo -u root cat` 里 `-u` 的取值 `root` 被当成命令名，
#     真正的 `cat` 反而整个丢失，`env -u FOO cat` 同理。
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "command,rule",
    [
        ("cat < /etc/passwd", "passwd"),
        ("ls > /tmp/out", "out"),
        ("echo hi > /tmp/rm", "rm"),
        ("echo hi >> /tmp/cat", "cat"),
        ("cat /etc/passwd > /tmp/x", "x"),
        # 粘连写法的目标同样是参数：修复前它会变成 ['passwd']，"禁用 passwd" 会拦下读文件
        ("cat</etc/passwd", "passwd"),
        # 参数路径本来就不该参与命令名判定（上一轮已修，这里防回归）
        ("rm -rf /tmp/test", "test"),
    ],
)
def test_redirection_target_is_never_treated_as_a_command_name(command, rule):
    """重定向目标是**参数**，不是新命令：不得命中"禁用某文件名"。"""
    assert matches_forbidden_command(command, rule) is False, (
        f"{command!r} 的重定向目标被误当成命令名（规则 {rule!r}）"
    )


@pytest.mark.parametrize(
    "command,rule",
    [
        ("cat < /etc/passwd", "cat"),
        ("ls > /tmp/out", "ls"),
        ("echo hi > /tmp/x", "echo"),
        # 重定向符仍必须把粘连的 token 切开，否则 `cat` 会消失（上一轮修的问题）
        ("cat</etc/passwd", "cat"),
    ],
)
def test_redirection_keeps_the_real_command_matchable(command, rule):
    """切重定向的同时，真正的命令名必须仍然可匹配。"""
    assert matches_forbidden_command(command, rule) is True, (
        f"{command!r} 的真正命令名没被识别出来（规则 {rule!r}）"
    )


@pytest.mark.parametrize(
    "command",
    [
        "sudo -u root cat /etc/passwd",
        "sudo --user root cat /etc/passwd",
        "sudo -uroot cat /etc/passwd",
        "sudo --user=root cat /etc/passwd",
        "env -u FOO cat /etc/passwd",
        "env --unset FOO cat /etc/passwd",
        "nice -n 10 cat /etc/passwd",
        "ionice -c 3 cat /etc/passwd",
        "stdbuf -o L cat /etc/passwd",
        "timeout 5 cat /etc/passwd",
        "sudo -u root env -u FOO cat /etc/passwd",
    ],
)
def test_wrapper_option_values_do_not_hide_the_real_command(command):
    """包装器的选项**取值**（如 `-u root`）不能被当成命令名，真正的命令不能丢。

    这是安全方向的漏判：一旦真正的命令丢失，"禁用 cat" 就形同虚设。
    """
    assert "cat" in shell_command_names(command), (
        f"{command!r} 里真正的 cat 丢失了，禁用规则会被绕过"
    )
    assert matches_forbidden_command(command, "cat") is True


@pytest.mark.parametrize(
    "command,rule",
    [
        ("sudo -u root cat", "root"),
        ("env -u FOO cat", "foo"),
        ("nice -n 10 cat", "10"),
    ],
)
def test_wrapper_option_values_are_not_commands(command, rule):
    """选项取值只是参数：不得命中"禁用 root/foo"这类规则。"""
    assert matches_forbidden_command(command, rule) is False, (
        f"{command!r} 的选项取值被误当成命令名（规则 {rule!r}）"
    )


def test_redirection_does_not_break_chained_segments():
    """`>` 从分隔符降级为"参数"后，真正的分隔符（`;` `&&` `|`）必须照旧工作。"""
    assert matches_forbidden_command("echo hi > /tmp/x; rm -rf /", "rm") is True
    assert matches_forbidden_command("echo hi > /tmp/x && cat /etc/passwd", "cat") is True
    assert matches_forbidden_command("echo hi > /tmp/x | cat", "cat") is True
    assert matches_forbidden_command("echo hi > /tmp/rm", "rm") is False, "重定向目标仍不当命令"
