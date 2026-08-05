"""Contract: DataPortalHome / TaskCenter emit navigation when Embed「我的资源」委托导航。"""

from pathlib import Path

import pytest

pytestmark = pytest.mark.no_infrastructure
ROOT = Path(__file__).resolve().parents[2]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_data_portal_home_embedded_guards_dashboard_navigation():
    source = _source("frontend/src/views/DataPortalHome.vue")
    # layout vs nav: PersonalCenter 仅传 embedded；Embed 弹层再传 delegate-navigation
    assert "embedded" in source
    assert "delegateNavigation" in source
    assert 'emit("open-report"' in source or "emit('open-report'" in source
    assert 'emit("open-conversation"' in source or "emit('open-conversation'" in source
    assert 'emit("open-question"' in source or "emit('open-question'" in source
    assert "if (!props.delegateNavigation)" in source or "if (props.delegateNavigation)" in source
    assert "if (props.embedded)" not in source  # 导航不得再绑 layout 的 embedded


def test_personal_center_data_portal_keeps_router_with_layout_embedded_only():
    center = _source("frontend/src/views/PersonalCenter.vue")
    portal = _source("frontend/src/views/DataPortalHome.vue")
    assert "DataPortalHome" in center
    assert "embedded" in center
    assert "delegate-navigation" not in center and "delegateNavigation" not in center
    assert "delegateNavigation" in portal
    assert 'path: "/dashboard/chat"' in portal


def test_task_center_embedded_blocks_notifications_dashboard_push():
    source = _source("frontend/src/views/TaskCenter.vue")
    assert "embedded" in source
    assert "openPersonalNotificationSettings" in source
    assert "props.embedded" in source or "embedded" in source
