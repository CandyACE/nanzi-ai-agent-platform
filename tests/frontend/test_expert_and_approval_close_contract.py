"""Contract: chat popovers expose visible close controls without changing selection behavior."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHAT_INPUT = ROOT / "frontend/src/components/embed/ChatInput.vue"
EXPERT_MENU = ROOT / "frontend/src/components/embed/ExpertCascadeMenu.vue"


def test_expert_menu_has_desktop_close_control_and_parent_wires_it():
    menu = EXPERT_MENU.read_text(encoding="utf-8")
    chat_input = CHAT_INPUT.read_text(encoding="utf-8")

    assert "(e: 'close'): void" in menu
    assert 'v-if="!fullWidth"' in menu
    assert 'aria-label="关闭专家中心"' in menu
    assert '@click.stop="emit(\'close\')"' in menu
    assert chat_input.count('@close="closeExpertCascade"') == 2
    assert chat_input.count('@close="showExpertSelector = false"') == 2


def test_approval_menu_has_visible_close_control():
    text = CHAT_INPUT.read_text(encoding="utf-8")

    assert 'aria-label="关闭工具批准方式"' in text
    assert '@click.stop="showApprovalMenu = false"' in text
