"""小程序微端签票接口测试。

前置条件：已导入 V170/V171（MySQL）或 V71/V72（PG）。
接口挂在 embed.py 的 router 上（v1_secured 之下，需 API Key）。
"""

import pytest
from sqlalchemy import func, select

from app.core.orm import AsyncSessionLocal
from app.models.user import User
from app.services.config_service import ConfigService

URL = "/api/v1/embed/miniprogram/session"
OPENID = "oApiTestOpenid000000000001"
APPID = "wx1ca87185956d0071"


async def _count_users_fresh() -> int:
    """用**全新 session** 计数。

    ⚠️ 不能复用测试的 db_session：MySQL 默认 REPEATABLE READ 下 before 的 SELECT
    已开启快照，接口在另一个 session 里提交建号后，同一 session 的 after 仍读到旧
    快照，于是 `after == before` 恒成立——这两条安全断言就成了空过（没有牙齿）。
    """
    async with AsyncSessionLocal() as fresh:
        return (await fresh.execute(select(func.count()).select_from(User))).scalar_one()


@pytest.fixture
async def miniprogram_on():
    """打开微端开关，结束后恢复原值。"""
    original = await ConfigService.get("miniprogram_enabled")
    await ConfigService.set_config(
        "miniprogram_enabled", "true", changed_by="pytest", change_reason="微端接口测试"
    )
    yield
    await ConfigService.set_config(
        "miniprogram_enabled",
        original if original is not None else "false",
        changed_by="pytest",
        change_reason="微端接口测试恢复",
    )


async def test_requires_api_key(client, miniprogram_on):
    resp = await client.post(URL, json={"openid": OPENID, "appid": APPID})
    assert resp.status_code in (401, 403), resp.text


async def test_user_without_impersonation_permission_is_forbidden_and_creates_no_account(
    client, valid_api_key, miniprogram_on
):
    """守护「权限校验前置于建号」——否则这是刷号入口。"""
    before = await _count_users_fresh()

    resp = await client.post(
        URL,
        json={"openid": OPENID, "appid": APPID},
        headers={"X-API-Key": valid_api_key},
    )

    assert resp.status_code == 403, resp.text

    after = await _count_users_fresh()
    assert after == before, "403 时不得产生任何新账号"


async def test_disabled_switch_returns_403(client, admin_api_key):
    # 迁移种子默认即为 false，这里显式确保
    await ConfigService.set_config("miniprogram_enabled", "false", changed_by="pytest")

    resp = await client.post(
        URL,
        json={"openid": OPENID, "appid": APPID},
        headers={"X-API-Key": admin_api_key},
    )

    assert resp.status_code == 403, resp.text
    assert "未开启" in resp.text


async def test_admin_gets_ticket_and_identity_summary(client, admin_api_key, miniprogram_on):
    resp = await client.post(
        URL,
        json={"openid": OPENID, "appid": APPID},
        headers={"X-API-Key": admin_api_key},
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    assert data["ticket"].startswith("emt_")
    assert data["expires_in"] > 0
    assert data["instance_id"].startswith("wx_")
    assert data["user"]["user_name"].startswith("wx_")
    assert data["user"]["is_new"] is True

    # 敏感字段绝不出现在响应里
    assert "api_key" not in resp.text
    assert OPENID not in resp.text


async def test_same_openid_is_idempotent(client, admin_api_key, miniprogram_on):
    first = await client.post(
        URL, json={"openid": OPENID, "appid": APPID}, headers={"X-API-Key": admin_api_key}
    )
    second = await client.post(
        URL, json={"openid": OPENID, "appid": APPID}, headers={"X-API-Key": admin_api_key}
    )

    assert first.status_code == 200 and second.status_code == 200, first.text + second.text
    a, b = first.json()["data"], second.json()["data"]

    assert a["user"]["user_id"] == b["user"]["user_id"]
    assert a["user"]["is_new"] is True
    assert b["user"]["is_new"] is False
    assert a["instance_id"] == b["instance_id"]


async def test_invalid_openid_returns_400_without_creating_account(
    client, admin_api_key, miniprogram_on
):
    before = await _count_users_fresh()

    resp = await client.post(
        URL,
        json={"openid": "bad openid", "appid": APPID},
        headers={"X-API-Key": admin_api_key},
    )

    assert resp.status_code == 400, resp.text

    after = await _count_users_fresh()
    assert after == before
