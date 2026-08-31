from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure
ROOT = Path(__file__).resolve().parents[2]
VIEW = ROOT / "frontend/src/views/AgentManagement.vue"
SERVICE = ROOT / "app/services/ai/agent_manager.py"


def test_main_agent_is_fixed_first_and_not_draggable():
    view = VIEW.read_text(encoding="utf-8")
    service = SERVICE.read_text(encoding="utf-8")

    assert view.count("const isMainAgent") == 1
    assert "isMainAgent" in view
    assert "isMainAgent(a)" in view
    assert "isMainAgent(agent)" in view
    assert "isMainAgent(sourceId)" in view
    assert "MAIN_GENERAL_AGENT_ID" in service
    assert "_is_main_general_agent_record(agent)" in service


def test_agent_management_header_keeps_title_single_line_and_limits_search_width():
    view = VIEW.read_text(encoding="utf-8")

    assert 'class="shrink-0 whitespace-nowrap text-xl font-bold text-gray-900 sm:text-2xl"' in view
    assert "sm:w-52 lg:w-56" in view
