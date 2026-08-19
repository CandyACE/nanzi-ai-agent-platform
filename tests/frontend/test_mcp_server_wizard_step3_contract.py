from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure

SOURCE = Path(
    "frontend/src/components/system/McpServerRegistry.vue"
).read_text()


def test_mcp_wizard_supports_three_steps_and_header_indicator():
    assert "const wizardStep = ref<1 | 2 | 3>(1)" in SOURCE
    assert "第三步：完成与发布指引" in SOURCE
    assert "wizardStep === 3" in SOURCE
    assert "CheckCircleIcon" in SOURCE


def test_mcp_wizard_step3_provides_publish_guidance_and_actions():
    assert "新接入的 MCP 工具默认处于" in SOURCE
    assert "未发布" in SOURCE
    assert "一键全部发布" in SOURCE
    assert "前往工具列表" in SOURCE
    assert "publishAllCreatedTools" in SOURCE
    assert "createdServer" in SOURCE


def test_mcp_server_all_unpublished_banner_and_quick_publish():
    assert "isAllToolsUnpublished" in SOURCE
    assert "publishAllCurrentServerTools" in SOURCE
    assert "当前服务下所有工具均为" in SOURCE
    assert "待发布" in SOURCE
    assert "无法搜索或调用" in SOURCE

