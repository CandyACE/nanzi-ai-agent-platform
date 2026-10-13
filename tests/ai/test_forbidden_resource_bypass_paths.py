"""禁用资源的「绕过路径」修复：引擎只读快速通道、身份缺失静默放行、快照写穿透。

这些缺陷都不在"正常路径"上，而藏在引擎判定顺序与文件系统的边上：命令黑名单挂在工具的
``check_permissions``（引擎 Step 4），但只读命令在 Step 3 的只读快速通道就拿到 ALLOW 了，
于是禁用 `cat` 之后 `cat /etc/passwd` 照跑。每条修复都配一个能复现该绕过的用例，避免以后
被"看起来还能拦"的测试骗过去。
"""

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from agentscope.permission import PermissionBehavior, PermissionDecision

pytestmark = pytest.mark.no_infrastructure


def _allow() -> PermissionDecision:
    return PermissionDecision(
        behavior=PermissionBehavior.ALLOW, message="ok", decision_reason="base"
    )


async def _run_deny_override(
    monkeypatch,
    tool_input,
    *,
    tool_forbidden=None,
    command_denied=None,
):
    """跑一遍真实的 ``ToolPermissionMiddleware``，让 next_handler 返回 ALLOW。

    ALLOW 正是引擎只读快速通道的形态（Step 3 直接放行、根本不进工具自查），因此
    这里返回 DENY 就等价于"deny_override 成功覆盖了快速通道"。
    """
    from app.services.ai.runtime.agentscope import tools as tools_mod
    from app.services.ai.runtime.agentscope.agent_runtime import build_runtime_middlewares

    calls: list[tuple] = []

    async def _tool_forbidden(tool_name, explicit_user_id=None):
        calls.append(("tool", tool_name))
        return tool_forbidden

    async def _command_forbidden(tool_name, received_input, explicit_user_id=None):
        calls.append(("command", tool_name, str((received_input or {}).get("command", ""))))
        return command_denied

    monkeypatch.setattr(tools_mod, "enforce_tool_forbidden", _tool_forbidden)
    monkeypatch.setattr(tools_mod, "enforce_command_forbidden", _command_forbidden)

    middleware = build_runtime_middlewares(user_id=9, conversation_id="c", agent_name="a")[0]

    async def next_handler(**_kwargs):
        return _allow()

    result = await middleware.on_check_permission(
        agent=SimpleNamespace(name="a"),
        input_kwargs={
            "tool_call": SimpleNamespace(name="Bash"),
            "tool": SimpleNamespace(name="Bash"),
            "tool_input": tool_input,
        },
        next_handler=next_handler,
    )
    return result, calls


@pytest.mark.asyncio
async def test_readonly_command_cannot_bypass_blacklist_via_fast_path(monkeypatch):
    """引擎只读快速通道先给 ALLOW，命令黑名单必须在 deny_override 里再拦一次。

    复现真实缺陷：``_enforce_command_blacklist`` 只挂在工具的 ``check_permissions``，
    而 `cat` 这类只读命令在 Step 3 就被 ALLOW，黑名单一次都不会被调用。
    """
    denied = PermissionDecision(
        behavior=PermissionBehavior.DENY,
        message="安全策略拦截：您的账号已被禁止在该智能体中执行包含 'cat' 的命令。",
        decision_reason="hit_user_forbidden_command",
        bypass_immune=True,
    )

    result, calls = await _run_deny_override(
        monkeypatch, {"command": "cat /etc/passwd"}, command_denied=denied
    )

    assert result.behavior == PermissionBehavior.DENY
    assert result.decision_reason == "hit_user_forbidden_command"
    assert [c[0] for c in calls] == ["tool", "command"], "命令校验必须真的被调用"
    assert calls[1][2] == "cat /etc/passwd", "命令原文要原样传给黑名单"


@pytest.mark.asyncio
async def test_not_forbidden_command_keeps_engine_decision(monkeypatch):
    """未被禁的命令不能被这次加固误伤。"""
    result, calls = await _run_deny_override(monkeypatch, {"command": "ls -al"})

    assert result.behavior == PermissionBehavior.ALLOW
    assert any(c[0] == "command" for c in calls)


@pytest.mark.asyncio
async def test_tool_deny_short_circuits_before_command_check(monkeypatch):
    """工具体本身被禁时直接返回，无需再看命令。"""
    denied = PermissionDecision(
        behavior=PermissionBehavior.DENY,
        message="forbidden",
        decision_reason="hit_user_forbidden_tool",
        bypass_immune=True,
    )

    result, calls = await _run_deny_override(
        monkeypatch, {"command": "cat /etc/passwd"}, tool_forbidden=denied
    )

    assert result.behavior == PermissionBehavior.DENY
    assert [c[0] for c in calls] == ["tool"]


@pytest.mark.asyncio
async def test_non_shell_tool_without_command_input_is_untouched(monkeypatch):
    """工具输入里没有 command（非 shell 工具）时不能因为这次加固改变结果。"""
    result, _ = await _run_deny_override(monkeypatch, {"path": "/tmp/x"})

    assert result.behavior == PermissionBehavior.ALLOW


def test_deny_override_wiring_is_contractually_present():
    """源码级契约：deny_override 同时接入工具与命令校验，缺一即回到绕过状态。"""
    source = Path(
        "app/services/ai/runtime/agentscope/agent_runtime.py"
    ).read_text(encoding="utf-8")
    override = source.split("async def _forbidden_tools_deny_override")[1].split(
        "middlewares: list[Any]"
    )[0]

    assert "enforce_tool_forbidden(" in override
    assert "enforce_command_forbidden(" in override
    assert "tool_input" in override


@pytest.mark.asyncio
async def test_missing_identity_warns_for_tool_and_command(monkeypatch, caplog):
    """身份缺失此前静默放行：必须留痕，否则线上无法区分「没禁」与「没身份所以没查」。

    降级方向本身不变（仍然是放行），只要求可观测。
    """
    from app.services.ai.runtime.agentscope import tools as tools_mod

    monkeypatch.setattr("app.core.context.get_current_agent_context", lambda: None)

    with caplog.at_level(logging.WARNING):
        tool_decision = await tools_mod.enforce_tool_forbidden("Bash")
        command_decision = await tools_mod.enforce_command_forbidden(
            "Bash", {"command": "cat /etc/passwd"}, None
        )

    assert tool_decision is None, "身份缺失仍然放行（不改变原有降级方向）"
    assert command_decision is None
    messages = [record.getMessage() for record in caplog.records]
    assert any("No user identity" in m and "tool blacklist" in m for m in messages)
    assert any("No user identity" in m and "command blacklist" in m for m in messages)


def test_identity_fallback_reads_the_key_production_actually_sets():
    """生产塞进 contextvar 的 user_info 键是 ``user_id``；回退读不到它就是死代码。"""
    from app.services.ai.runtime.agentscope.workspace import _resolve_identity_user_id

    assert _resolve_identity_user_id({"user_id": 12}) == 12
    assert _resolve_identity_user_id({"id": 7}) == 7
    assert _resolve_identity_user_id({"u_id_val": 3}) == 3
    assert _resolve_identity_user_id({}) is None
    assert _resolve_identity_user_id(None) is None


@pytest.mark.asyncio
async def test_skill_policy_identity_fallback_also_covers_user_id(monkeypatch):
    """技能侧走的是另一个回退点，键列表必须同样包含 ``user_id``。

    生产只把原始 user_info（键为 ``user_id``）塞进 contextvar，若回退读不到这个键，
    它就恒为 None —— 也就是说这个回退是死代码，只能靠 agent ctx 兜底。
    """
    from app.services.ai.skills import policy as policy_mod

    monkeypatch.setattr("app.core.context.get_current_agent_context", lambda: None)
    monkeypatch.setattr(
        "app.utils.context.current_user_info",
        SimpleNamespace(get=lambda: {"user_id": 21}),
    )

    seen: list[int] = []

    class _Service:
        def __init__(self, _session):
            pass

        async def get_user_permissions(self, user_id):
            seen.append(user_id)
            return SimpleNamespace(
                roles=[], permissions=SimpleNamespace(forbidden_skills=["docx"])
            )

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return False

    monkeypatch.setattr("app.core.orm.AsyncSessionLocal", lambda: _Session())
    monkeypatch.setattr("app.services.permission_service.PermissionService", _Service)

    resolved = await policy_mod.get_forbidden_skill_ids()

    assert seen == [21], "回退必须真的拿到 user_id（否则恒为 None、永不查库）"
    assert resolved == {"docx"}


def test_session_snapshot_is_a_real_copy_not_a_hardlink(tmp_path):
    """会话快照与源技能不能共享 inode：否则写会话副本会改到平台技能源文件。"""
    from app.services.ai.runtime.agentscope.workspace import _hardlink_or_copy2

    src = tmp_path / "SKILL.md"
    src.write_text("original", encoding="utf-8")
    dst = tmp_path / "session-copy.md"

    _hardlink_or_copy2(str(src), str(dst))
    dst.write_text("modified through the session snapshot", encoding="utf-8")

    assert src.read_text(encoding="utf-8") == "original", "写会话副本不得影响技能源文件"


def test_snapshot_copy_helper_no_longer_links():
    """源码级契约：硬链接会让会话快照与源技能共享 inode，必须已改成真实复制。"""
    source = Path(
        "app/services/ai/runtime/agentscope/workspace.py"
    ).read_text(encoding="utf-8")
    helper = source.split("def _hardlink_or_copy2")[1].split("def _forbidden_skill_hashes")[0]

    # 注释里会解释"历史上用过 os.link"，所以只断言没有实际调用
    assert "os.link(" not in helper
    assert "shutil.copy2(" in helper


def test_dropping_a_mounted_forbidden_skill_is_logged(caplog):
    """技能被剔除此前完全静默：用户看到「已挂载」却拿不到，线上也查不到线索。"""
    from app.services.ai.skills.policy import drop_forbidden_skill_items

    items = [
        {"type": "skill", "url": "docx", "name": "Word"},
        {"type": "skill", "url": "pdf", "name": "PDF"},
        {"type": "file", "url": "docx", "name": "同名文件不受影响"},
    ]

    with caplog.at_level(logging.WARNING):
        kept = drop_forbidden_skill_items(items, {"docx"})

    assert [item["url"] for item in kept] == ["pdf", "docx"], "只剔除技能类型的同名项"
    assert any("Dropped explicitly mounted forbidden skill" in r.getMessage() for r in caplog.records)
