from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.no_infrastructure


def test_dashboard_recent_users_card_represents_last_activity():
    source = (ROOT / "frontend/src/components/dashboard/RecentUsersCard.vue").read_text(
        encoding="utf-8"
    )

    assert "活跃用户" in source
    assert "user.last_active" in source
    assert "user.created_at" not in source
