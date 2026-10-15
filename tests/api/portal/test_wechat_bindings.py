"""管理端「微信绑定」视图接口测试。

前置条件：已导入 V170/V171（MySQL）或 V71/V72（PG）。
"""

import pytest
from sqlalchemy import select

from app.models.user import User
from app.models.wechat_binding import WechatBinding

BINDINGS_URL = "/api/portal/management/wechat-bindings"
USERS_URL = "/api/portal/management/users"

OPENID = "oMgmtTestOpenid000000000001"
UNIONID = "uMgmtTestUnionid0000000001"
APPID = "wx1ca87185956d0071"


@pytest.fixture
async def bound_user(db_session):
    """给 seed 出来的 test_user 造一条微信绑定。

    ⚠️ 与计划的两处偏差（计划原文用 "TestUser"，且直接 add+commit）：
    1. seed 账号的 user_name 是 ``test_user``/``test_admin``（``TestUser_`` 只是
       API Key 前缀，tests/conftest.py:122-136），库里不存在 "TestUser"；
    2. seed 账号在 TEST_DATA_KEEP_USER_NAMES 白名单里，绑定行不会被兜底清理，
       直接 add+commit 会在第二次运行时撞 (appid, openid) 唯一键——故做 get-or-create。
    """
    user = (
        await db_session.execute(select(User).where(User.user_name == "test_user"))
    ).scalar_one()

    binding = (
        await db_session.execute(
            select(WechatBinding).where(
                WechatBinding.appid == APPID, WechatBinding.openid == OPENID
            )
        )
    ).scalar_one_or_none()
    if binding is None:
        binding = WechatBinding(user_id=user.id, appid=APPID, openid=OPENID, unionid=UNIONID)
        db_session.add(binding)
        await db_session.commit()
        await db_session.refresh(binding)
    return user, binding


async def test_list_requires_permission(client, valid_api_key):
    """普通用户没有 menu:system:users，不得看到绑定列表。"""
    resp = await client.get(BINDINGS_URL, headers={"X-API-Key": valid_api_key})
    assert resp.status_code in (401, 403), resp.text


async def test_list_masks_openid_and_unionid(client, admin_api_key, bound_user):
    resp = await client.get(BINDINGS_URL, headers={"X-API-Key": admin_api_key})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] >= 1

    row = next(r for r in body["items"] if r["user_id"] == bound_user[0].id)

    # 列表不得出现完整值
    assert OPENID not in resp.text, "列表接口不得下发完整 openid"
    assert UNIONID not in resp.text, "列表接口不得下发完整 unionid"

    # 脱敏形态：首 6 + **** + 尾 4
    assert row["openid_masked"] == f"{OPENID[:6]}****{OPENID[-4:]}"
    assert row["user_name"] == "test_user"
    assert row["appid"] == APPID


async def test_raw_identity_requires_edit_level_permission(
    client, valid_api_key, admin_api_key, bound_user
):
    """明文取用必须比列表更严（element:user:edit）。"""
    _, binding = bound_user
    url = f"{BINDINGS_URL}/{binding.id}/identity"

    denied = await client.get(url, headers={"X-API-Key": valid_api_key})
    assert denied.status_code in (401, 403), denied.text
    assert OPENID not in denied.text

    allowed = await client.get(url, headers={"X-API-Key": admin_api_key})
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["openid"] == OPENID
    assert allowed.json()["unionid"] == UNIONID


async def test_raw_identity_404_for_unknown_binding(client, admin_api_key):
    resp = await client.get(f"{BINDINGS_URL}/999999999/identity", headers={"X-API-Key": admin_api_key})
    assert resp.status_code == 404, resp.text


async def test_user_list_marks_wechat_bound(client, admin_api_key, bound_user):
    """用户列表要能一眼看出「这人是微端用户」。"""
    user, _ = bound_user

    resp = await client.get(
        USERS_URL,
        params={"search": user.user_name},
        headers={"X-API-Key": admin_api_key},
    )

    assert resp.status_code == 200, resp.text
    row = next(r for r in resp.json()["items"] if r["id"] == user.id)
    assert row["wechat_bound"] is True


async def test_user_list_marks_unbound_as_false(client, admin_api_key):
    """没有绑定的账号必须是 False——否则标识失去意义。"""
    resp = await client.get(
        USERS_URL, params={"search": "test_admin"}, headers={"X-API-Key": admin_api_key}
    )

    assert resp.status_code == 200, resp.text
    row = next(r for r in resp.json()["items"] if r["user_name"] == "test_admin")
    assert row["wechat_bound"] is False
