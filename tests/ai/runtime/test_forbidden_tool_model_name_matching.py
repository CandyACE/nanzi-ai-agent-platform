"""禁用工具拦截：必须同时命中平台名与「模型侧调用名」。

背景（缺陷 B）：MCP 工具注册给模型时名字必须合法（OpenAI Function Calling 只接受
``^[a-zA-Z0-9_-]+$``），因此 ``mcp_factory`` 用 ``build_model_tool_name()`` 把平台名
``jira_search`` / ``crm:query`` 变成 ``mcp_<可读名>_<hash10>``；而禁用目录里存的是平台名。
拦截侧若只做内置别名扩展，MCP 工具的禁用就是"配置了但不生效"。
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services.ai.runtime.agentscope.tools import enforce_tool_forbidden
from app.services.ai.tools.model_tool_name import build_model_tool_name


pytestmark = pytest.mark.no_infrastructure


class _FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False


def _permission_set(forbidden_tools):
    return SimpleNamespace(
        roles={"user"},
        permissions=SimpleNamespace(forbidden_tools=list(forbidden_tools)),
    )


async def _decide(tool_name: str, forbidden_tools):
    with patch("app.core.orm.AsyncSessionLocal", return_value=_FakeSession()), patch(
        "app.services.permission_service.PermissionService"
    ) as service_cls:
        service_cls.return_value.get_user_permissions = AsyncMock(
            return_value=_permission_set(forbidden_tools)
        )
        return await enforce_tool_forbidden(tool_name, 1)


@pytest.mark.asyncio
async def test_mcp_tool_is_denied_via_its_model_facing_name():
    """目录里勾的是 `jira_search`，运行时传进来的是 `mcp_jira_search_<hash>`。"""
    runtime_name = build_model_tool_name("jira_search")
    assert runtime_name != "jira_search", "前提：MCP 运行时名确实被变形了"

    decision = await _decide(runtime_name, ["jira_search"])

    assert decision is not None
    assert decision.decision_reason == "hit_user_forbidden_tool"


@pytest.mark.asyncio
async def test_namespaced_mcp_tool_is_denied_via_its_model_facing_name():
    """平台命名空间形式 `server:tool` 同样要拦得住。"""
    decision = await _decide(build_model_tool_name("crm:query"), ["crm:query"])

    assert decision is not None
    assert decision.decision_reason == "hit_user_forbidden_tool"


@pytest.mark.asyncio
async def test_builtin_tool_and_alias_matching_is_unchanged():
    """既有内置语义（双向别名扩展）不能因为这次修改而改变。"""
    assert await _decide("write_file", ["write_file"]) is not None
    assert await _decide("Write", ["write_file"]) is not None
    assert await _decide("write_file", ["Write"]) is not None


@pytest.mark.asyncio
async def test_unrelated_tools_are_still_allowed():
    """展开名字不得造成误拦：不同工具、以及同可读名但不同哈希的工具都应放行。"""
    assert await _decide(build_model_tool_name("other_tool"), ["jira_search"]) is None
    assert await _decide("read_file", ["jira_search"]) is None
    # hash 的存在意义：可读名相同但原名不同的工具不是同一个工具
    assert await _decide(build_model_tool_name("jira_search_v2"), ["jira_search"]) is None
