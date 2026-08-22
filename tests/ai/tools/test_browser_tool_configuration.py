import pytest

from app.services.ai.tools.registry import ToolRegistry


pytestmark = pytest.mark.no_infrastructure


BROWSER_AUTOMATION_TOOL_NAMES = [
    "browser_open",
    "browser_snapshot",
    "browser_click",
    "browser_fill",
    "browser_scroll",
    "browser_press",
    "browser_wait_for",
    "browser_select_option",
    "browser_read_visible",
    "browser_hover",
    "browser_drag",
    "browser_back",
    "browser_forward",
    "browser_reload",
    "browser_tabs",
    "browser_switch_tab",
    "browser_close_tab",
    "browser_upload",
    "browser_download",
]


def test_browser_automation_tools_are_not_system_implicit_tools():
    implicit_names = {
        getattr(tool, "name", "")
        for tool in ToolRegistry.get_system_implicit_tools()
    }

    assert implicit_names.isdisjoint(BROWSER_AUTOMATION_TOOL_NAMES)


@pytest.mark.asyncio
async def test_browser_automation_tools_remain_explicitly_configurable():
    specs = await ToolRegistry.get_runtime_tools(BROWSER_AUTOMATION_TOOL_NAMES)

    assert [spec.name for spec in specs] == BROWSER_AUTOMATION_TOOL_NAMES
