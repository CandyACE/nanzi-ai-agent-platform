"""Contract: Embed「我的资源」弹层壳与懒加载 Tab。"""

from pathlib import Path

import pytest

pytestmark = pytest.mark.no_infrastructure
ROOT = Path(__file__).resolve().parents[2]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_personal_resources_modal_shell_and_tabs():
    modal = _source("frontend/src/components/embed/PersonalResourcesModal.vue")
    assert "我的资源" in modal
    assert "defineAsyncComponent" in modal
    assert "PersonalMemoryPanel" in modal
    assert "PersonalTokenUsage" in modal
    assert "DataPortalHome" in modal
    assert "SkillsManagement" in modal
    assert "McpManagement" in modal
    assert "TaskCenter" in modal
    assert "update:visible" in modal
    assert "activeTab" in modal
    # Embed 弹层须传 delegate-navigation；PersonalCenter 仅传 embedded
    assert "delegate-navigation" in modal or "delegateNavigation" in modal
