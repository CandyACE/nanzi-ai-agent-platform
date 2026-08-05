from pathlib import Path

import pytest

pytestmark = pytest.mark.no_infrastructure
ROOT = Path(__file__).resolve().parents[2]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_personal_memory_panel_exists_and_is_used_by_personal_center():
    panel = _source("frontend/src/components/personal/PersonalMemoryPanel.vue")
    center = _source("frontend/src/views/PersonalCenter.vue")
    assert "每日摘要" in panel
    assert "会话摘要" in panel
    assert "长期记忆" in panel
    assert "/api/portal/memory/my/" in panel
    assert "PersonalMemoryPanel" in center
