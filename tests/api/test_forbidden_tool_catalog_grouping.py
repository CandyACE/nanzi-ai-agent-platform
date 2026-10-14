"""禁用工具目录 v2：候选的分组字段（group_key / group）契约。

设计见 docs/superpowers/specs/2026-10-13-forbidden-tool-grouping-design.md §3.1：
分组归属与展示文案由后端决定，前端只按 group_key 聚合、直接渲染 group。
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.portal.endpoints import tools as tools_endpoint
from app.services.ai.tools import forbidden_catalog


pytestmark = pytest.mark.no_infrastructure

EXPECTED_BUILTIN_GROUPS = {
    "sandbox": ("builtin:sandbox", "沙箱命令"),
    "file": ("builtin:file", "文件操作"),
    "process": ("builtin:process", "进程管理"),
    "knowledge": ("builtin:knowledge", "知识库"),
}


def _db_with(api_tools, mcp_tools):
    """按调用顺序依次返回自定义 API 工具与 MCP 工具的结果集。"""
    db = MagicMock()
    db.execute = AsyncMock(
        side_effect=[
            SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: api_tools)),
            SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: mcp_tools)),
        ]
    )
    return db


def test_builtin_candidates_carry_category_group_labels():
    """内置候选按 category 归组，标签是给用户看的中文子组名。"""
    for candidate in forbidden_catalog.BUILTIN_FORBIDDEN_TOOL_CANDIDATES:
        expected_key, expected_label = EXPECTED_BUILTIN_GROUPS[candidate.category]

        assert candidate.group_key == expected_key
        assert candidate.group == expected_label


def test_unknown_builtin_category_falls_back_instead_of_raising():
    """未识别的 category 不能抛错，也不能产生空子组。"""
    assert forbidden_catalog.builtin_group("sandbox") == ("builtin:sandbox", "沙箱命令")
    assert forbidden_catalog.builtin_group("mystery") == ("builtin:mystery", "其他内置工具")
    assert forbidden_catalog.builtin_group("") == ("builtin:other", "其他内置工具")
    assert forbidden_catalog.builtin_group(None) == ("builtin:other", "其他内置工具")


def test_api_tool_group_uses_business_group_then_ungrouped_fallback():
    assert forbidden_catalog.api_tool_group("外部服务") == (
        "api:外部服务",
        "自定义 API · 外部服务",
    )
    assert forbidden_catalog.api_tool_group(None) == (
        "api:__ungrouped__",
        "自定义 API · 未分组",
    )
    assert forbidden_catalog.api_tool_group("   ") == (
        "api:__ungrouped__",
        "自定义 API · 未分组",
    )


def test_mcp_tool_group_uses_server_name_then_unknown_fallback():
    assert forbidden_catalog.mcp_tool_group("CRM") == ("mcp:CRM", "MCP · CRM")
    assert forbidden_catalog.mcp_tool_group(None) == ("mcp:__unknown__", "MCP · 未知服务")
    assert forbidden_catalog.mcp_tool_group("") == ("mcp:__unknown__", "MCP · 未知服务")


@pytest.mark.asyncio
async def test_catalog_response_exposes_grouping_fields_and_keeps_existing_contract():
    """新增字段不得挤掉既有字段，也不得改变「内置在前」的顺序。"""
    api_tool = SimpleNamespace(name="fetch_weather", description="天气查询", group_name="外部服务")
    ungrouped_api_tool = SimpleNamespace(name="send_email", description=None, group_name=None)
    mcp_tool = SimpleNamespace(
        tool_name="crm:query",
        tool_description="CRM 查询",
        server=SimpleNamespace(server_name="CRM", scope="global"),
    )
    orphan_mcp_tool = SimpleNamespace(
        tool_name="legacy:ping",
        tool_description=None,
        server=None,
    )

    response = await tools_endpoint.list_forbidden_tool_catalog(
        _db_with([api_tool, ungrouped_api_tool], [mcp_tool, orphan_mcp_tool]),
        {"role": "admin", "user_id": 1},
    )
    candidates = {candidate["id"]: candidate for candidate in response["candidates"]}

    assert list(candidates)[:3] == ["exec_command", "write_file", "edit_file"]

    # 既有字段一个都不能少
    for candidate in response["candidates"]:
        assert set(candidate) == {
            "id",
            "label",
            "description",
            "category",
            "aliases",
            "group_key",
            "group",
        }

    assert candidates["exec_command"]["group_key"] == "builtin:sandbox"
    assert candidates["exec_command"]["group"] == "沙箱命令"
    assert candidates["fetch_weather"]["group"] == "自定义 API · 外部服务"
    assert candidates["send_email"]["group"] == "自定义 API · 未分组"
    assert candidates["crm:query"]["group"] == "MCP · CRM"
    # server 缺失的 MCP 工具不能抛错，归入「未知服务」
    assert candidates["legacy:ping"]["group"] == "MCP · 未知服务"
