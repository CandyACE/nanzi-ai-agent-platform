import os
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.services.ai.runtime.agentscope.tools import RuntimeToolSpec
from app.services.ai.runtime.agentscope.workspace import resolve_session_workdir


pytestmark = pytest.mark.no_infrastructure


@pytest.fixture(autouse=True)
def _local_policy_without_redis(monkeypatch):
    """避免真实 get_local_workspace 依赖 Redis 读取 sandbox_policy。

    这些测试标记了 no_infrastructure（不初始化 DB/Redis），而 get_local_workspace
    内部会 ConfigService.get("sandbox_policy", ...) 走 Redis。这里固定返回 local
    policy，使测试在零 Redis 环境下自足可跑，且不依赖测试执行顺序。
    """
    monkeypatch.setattr(
        "app.services.config_service.ConfigService.get",
        AsyncMock(return_value="local"),
    )


async def _noop_tool(**kwargs):
    return kwargs


@pytest.mark.asyncio
async def test_bind_configured_tools_to_workspace_sets_bash_cwd_without_injecting_extras(
    tmp_path,
    monkeypatch,
):
    from app.services.ai.runtime.agentscope.workspace import (
        bind_configured_tools_to_workspace,
        clear_workspace_cache,
        get_local_workspace,
    )
    from app.services.ai.tools.registry import ToolRegistry

    clear_workspace_cache()

    async def _root():
        return str(tmp_path)

    monkeypatch.setattr(
        "app.services.ai.runtime.agentscope.workspace.resolve_workspace_root",
        _root,
    )

    workspace = await get_local_workspace(
        user_id=1,
        user_name="alice",
        conversation_id="conv-bash",
    )
    assert workspace is not None
    _, local_ws = workspace

    specs = await ToolRegistry.get_runtime_tools(["exec_command", "search_knowledge_base"])
    unbound_bash = next(spec for spec in specs if spec.name == "Bash")
    assert getattr(unbound_bash.native_tool, "_cwd", None) in (None, "")

    bound = await bind_configured_tools_to_workspace(workspace, specs)
    expected_cwd = resolve_session_workdir(
        root=str(tmp_path),
        user_id=1,
        user_name="alice",
        conversation_id="conv-bash",
    )

    assert [spec.name for spec in bound] == [spec.name for spec in specs]
    bound_bash = next(spec for spec in bound if spec.name == "Bash")
    assert os.path.abspath(bound_bash.native_tool._cwd) == os.path.abspath(expected_cwd)
    assert os.path.abspath(bound_bash.native_tool._cwd) == os.path.abspath(local_ws.workdir)
    from app.services.ai.runtime.conversation_run_subprocess import CancellableLocalBackend

    assert isinstance(bound_bash.native_tool._backend, CancellableLocalBackend)
    assert "Read" not in [spec.name for spec in bound]


@pytest.mark.asyncio
async def test_bind_configured_tools_to_workspace_is_noop_without_workspace():
    from app.services.ai.runtime.agentscope.workspace import (
        bind_configured_tools_to_workspace,
    )
    spec = RuntimeToolSpec(
        name="Bash",
        description="bash",
        parameters_schema={"type": "object", "properties": {}},
        source_type="system",
        callable=_noop_tool,
        permission_scope="ask",
    )
    bound = await bind_configured_tools_to_workspace(None, [spec])
    assert bound == [spec]


@pytest.mark.asyncio
async def test_bind_configured_tools_to_workspace_ignores_non_list_list_tools():
    from unittest.mock import MagicMock

    from app.services.ai.runtime.agentscope.workspace import (
        bind_configured_tools_to_workspace,
    )

    spec = RuntimeToolSpec(
        name="Bash",
        description="bash",
        parameters_schema={"type": "object", "properties": {}},
        source_type="system",
        callable=_noop_tool,
        permission_scope="ask",
    )
    fake_workspace = MagicMock()
    bound = await bind_configured_tools_to_workspace(fake_workspace, [spec])
    assert bound == [spec]


def test_agentscope_skill_catalog_stays_disconnected_from_production_tooling():
    """生产不得把技能清单交给 AgentScope。

    AgentScope 会把 ``skills_or_loaders`` 渲染成 ``<agent-skills><dir>…</dir>`` 塞进
    prompt，而 ``Skill.dir`` 是**宿主绝对路径**（Docker 部署下形如
    ``/app/data/agent_workspaces/<user_key>/sessions/<cid>/skills/...``），沙箱里的模型
    照着去 Bash/Read 必然找不到（技能自带脚本尤其明显）。

    本仓库曾有一套 ``build_workspace_toolkit`` 接入（含把 ``Skill.dir`` 映射成
    ``/workspace/...`` 的护栏），因生产无调用方已整体删除。若确实要接回，必须同时把
    ``Skill.dir`` 映射为沙箱可见路径，并把这条契约改成「必须映射」的正向断言——背景见
    ``tests/CHECKLIST.md`` 2026-10-14 的「AgentScope 技能目录路径护栏」条目。
    """
    app_root = Path(__file__).resolve().parents[3] / "app"
    offenders = [
        path.relative_to(app_root.parent).as_posix()
        for path in app_root.rglob("*.py")
        if "skills_or_loaders" in path.read_text(encoding="utf-8")
    ]
    assert offenders == [], f"AgentScope 技能清单不得接入生产：{offenders}"
