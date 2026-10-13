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

        async def get_user_permissions(self, user_id):
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

        async def get_user_permissions(self, _user_id):
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

        async def get_user_permissions(self, _user_id):
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
