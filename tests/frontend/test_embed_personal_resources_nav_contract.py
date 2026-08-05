"""Contract: DataPortalHome / TaskCenter emit navigation when embedded in Embed「我的资源」."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.no_infrastructure
ROOT = Path(__file__).resolve().parents[2]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_data_portal_home_embedded_guards_dashboard_navigation():
    source = _source("frontend/src/views/DataPortalHome.vue")
    assert "embedded" in source
    assert 'emit("open-report"' in source or "emit('open-report'" in source
    assert 'emit("open-conversation"' in source or "emit('open-conversation'" in source
    assert 'emit("open-question"' in source or "emit('open-question'" in source
    assert "if (!props.embedded)" in source or "if (props.embedded)" in source


def test_task_center_embedded_blocks_notifications_dashboard_push():
    source = _source("frontend/src/views/TaskCenter.vue")
    assert "embedded" in source
    assert "openPersonalNotificationSettings" in source
    assert "props.embedded" in source or "embedded" in source
