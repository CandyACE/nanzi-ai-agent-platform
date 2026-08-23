import os
from unittest.mock import AsyncMock

import pytest

from app.services.ai.runtime.agentscope.tools import RuntimeToolSpec
from app.services.ai.runtime.agentscope.workspace import (
    build_workspace_toolkit,
    is_workspace_managed_tool_spec,
    resolve_session_workdir,
)


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
async def test_build_workspace_toolkit_uses_workspace_builtins_and_keeps_platform_tools(
    tmp_path,
    monkeypatch,
):
    from app.services.ai.runtime.agentscope.workspace import get_local_workspace

    async def _root():
        return str(tmp_path)

    monkeypatch.setattr(
        "app.services.ai.runtime.agentscope.workspace.resolve_workspace_root",
        _root,
    )
    monkeypatch.setattr(
        "app.services.ai.runtime.agentscope.workspace.discover_platform_skill_paths",
        lambda **kwargs: [],
    )

    workspace = await get_local_workspace(user_id="u1", conversation_id="c1")
    assert workspace is not None
    _, local_ws = workspace

    builtin_spec = RuntimeToolSpec(
        name="Bash",
        description="bash",
        parameters_schema={"type": "object", "properties": {}},
        source_type="system",
        callable=_noop_tool,
        permission_scope="ask",
    )
    platform_spec = RuntimeToolSpec(
        name="search_knowledge_base",
        description="kb",
        parameters_schema={"type": "object", "properties": {}},
        source_type="static",
        callable=_noop_tool,
        permission_scope="read",
    )
    skill_spec = RuntimeToolSpec(
        name="list_available_skills",
        description="skills",
        parameters_schema={"type": "object", "properties": {}},
        source_type="static",
        callable=_noop_tool,
        permission_scope="read",
    )

    toolkit = await build_workspace_toolkit(
        local_ws,
        [builtin_spec, platform_spec, skill_spec],
        user_info={"user_id": "u1", "user_name": "alice", "role": "user"},
    )

    schemas = await toolkit.get_tool_schemas()
    tool_names = [item["function"]["name"] for item in schemas]
    assert "Bash" in tool_names
    assert "Read" in tool_names
    assert "search_knowledge_base" in tool_names
    assert "list_available_skills" not in tool_names
    assert tool_names.count("Bash") == 1


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


def test_is_workspace_managed_tool_spec_matches_aliases():
    spec = RuntimeToolSpec(
        name="exec_command",
        description="bash alias",
        parameters_schema={"type": "object", "properties": {}},
        source_type="system",
        callable=_noop_tool,
        permission_scope="ask",
    )
    assert is_workspace_managed_tool_spec(spec) is True
