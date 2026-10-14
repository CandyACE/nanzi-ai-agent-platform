"""管理端重置凭据必须吊销该用户既有会话。

回归背景：`reset_user_api_key`（管理员重置 API Key）与管理员 `set_user_password`
（代设登录密码）原先只换掉凭据本身。会话令牌是独立于 `api_key_hash` 的 Redis 键
（`auth:api_key:{sha256(sess_token)}`），不按 user_id 成批吊销就依然有效——于是
「管理员发现账号被盗 → 重置 Key / 代设密码」之后，对方手里的会话仍然能用，
重置等于没重置。

注意：用户**自助**重置 API Key 是唯一例外，它刻意不退出现有会话（重置后会把
新 Key 重新写进当前 Cookie，见 `auth.py` 中该端点的说明与
`tests/api/portal/test_reset_my_api_key.py`），本文件不覆盖该路径。
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.api.portal.endpoints.management import (
    SetPasswordRequest,
    reset_user_api_key,
    set_user_password,
)
from app.services.auth_service import AuthService


pytestmark = pytest.mark.no_infrastructure

ADMIN = {"user_id": "1", "user_name": "admin", "role": "admin"}


@pytest.mark.asyncio
async def test_admin_reset_key_revokes_existing_sessions():
    """重置 API Key 后，该用户既有会话必须被吊销。"""
    db = AsyncMock()
    db.get = AsyncMock(return_value=SimpleNamespace(id=9, api_key_hash="old-hash"))

    with patch.object(
        AuthService, "reset_api_key", new_callable=AsyncMock, return_value="NEW_KEY"
    ), patch.object(
        AuthService, "invalidate_user_auth_cache", new_callable=AsyncMock
    ) as invalidate:
        result = await reset_user_api_key(user_id=9, admin=ADMIN, db=db)

    assert result["api_key"] == "NEW_KEY"
    invalidate.assert_awaited_once()
    assert invalidate.await_args.args[0] == 9
    # 必须是显式「吊销会话」，否则默认只清认证缓存、会话照旧可用
    assert invalidate.await_args.kwargs.get("revoke_sessions") is True


@pytest.mark.asyncio
async def test_admin_set_password_revokes_existing_sessions():
    """管理员代设/重置密码后，该用户既有会话必须被吊销。"""
    db = AsyncMock()
    db.get = AsyncMock(return_value=SimpleNamespace(id=9, user_name="alice"))

    with patch.object(
        AuthService, "set_user_password", new_callable=AsyncMock, return_value=True
    ), patch.object(
        AuthService, "revoke_sessions_for_user", new_callable=AsyncMock
    ) as revoke:
        result = await set_user_password(
            user_id=9,
            request=SetPasswordRequest(password="Secr3t!2026"),
            admin=ADMIN,
            db=db,
        )

    assert result["status"] == "success"
    revoke.assert_awaited_once()
    assert revoke.await_args.args[0] == 9
