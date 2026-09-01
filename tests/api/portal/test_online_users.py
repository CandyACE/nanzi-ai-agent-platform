"""在线用户统计测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api.portal.endpoints import dashboard


pytestmark = pytest.mark.no_infrastructure


@pytest.mark.asyncio
async def test_online_users_endpoint_reads_presence_users(monkeypatch):
    presence_users = [
        {
            "user_id": "1",
            "user_name": "admin",
            "real_name": "管理员",
            "role": "admin",
            "last_active": "1000",
        },
        {
            "user_id": "2",
            "user_name": "alice",
            "real_name": "Alice",
            "role": "user",
            "last_active": "900",
        },
    ]
    presence = SimpleNamespace(
        list_active_users=AsyncMock(return_value=presence_users)
    )
    monkeypatch.setattr(dashboard, "OnlinePresenceService", presence, raising=False)
    monkeypatch.setattr(dashboard, "get_redis", AsyncMock(return_value=object()))

    result = await dashboard.get_online_users({"role": "admin"})

    assert result == {"count": 2, "users": presence_users}
    presence.list_active_users.assert_awaited_once()
