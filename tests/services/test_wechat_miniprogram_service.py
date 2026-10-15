"""小程序微端服务层测试。

- 模型契约与纯函数测试不连库（no_infrastructure）；
- 身份解析测试需要真实数据库，依赖已导入的 V170/V171（或 PG 的 V71/V72）。

注意：这里不能用模块级 pytestmark——本文件同时含有需要数据库的集成测试。
"""

import pytest


# --------------------------------------------------------------------------- #
# 模型契约（不连库）
# --------------------------------------------------------------------------- #

@pytest.mark.no_infrastructure
def test_binding_model_matches_migration_shape():
    from app.models.wechat_binding import WechatBinding

    assert WechatBinding.__tablename__ == "ai_agent_wechat_bindings"

    columns = {c.name for c in WechatBinding.__table__.columns}
    assert columns == {
        "id",
        "user_id",
        "appid",
        "openid",
        "unionid",
        "created_at",
        "last_login_at",
    }

    # (appid, openid) 唯一约束必须声明在 ORM 里，否则代码与迁移会漂移
    unique_columns = {
        tuple(sorted(c.name for c in constraint.columns))
        for constraint in WechatBinding.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("appid", "openid") in unique_columns


# --------------------------------------------------------------------------- #
# 纯函数（不连库）
# --------------------------------------------------------------------------- #

@pytest.mark.no_infrastructure
def test_derive_instance_id_is_stable_and_user_specific():
    from app.services.wechat_miniprogram_service import derive_instance_id

    a1 = derive_instance_id("oABC1234567890123456789012")
    a2 = derive_instance_id("oABC1234567890123456789012")
    b = derive_instance_id("oZZZ1234567890123456789012")

    assert a1 == a2, "同一 openid 必须派生出同一 instance_id（会话分桶需稳定）"
    assert a1 != b, "不同 openid 不得碰撞，否则会共用会话分桶"
    assert a1.startswith("wx_")
    assert len(a1) == 3 + 16


@pytest.mark.no_infrastructure
def test_derive_user_name_is_stable_and_does_not_leak_openid():
    from app.services.wechat_miniprogram_service import derive_user_name

    openid = "oABC1234567890123456789012"
    name = derive_user_name(openid)

    assert name == derive_user_name(openid)
    assert name.startswith("wx_")
    assert openid not in name, "账号名不得包含明文 openid"


@pytest.mark.no_infrastructure
@pytest.mark.parametrize(
    "openid,expected",
    [
        ("oABC1234567890123456789012", True),          # 28 位典型 openid
        ("abc_DEF-12345678901234567890", True),        # 允许 - 和 _
        ("", False),
        ("short", False),
        ("has space 12345678901234567", False),
        ("中文openid123456789012345", False),
        ("a" * 65, False),                             # 超长
    ],
)
def test_is_valid_openid(openid, expected):
    from app.services.wechat_miniprogram_service import is_valid_openid

    assert is_valid_openid(openid) is expected


# --------------------------------------------------------------------------- #
# 身份解析与开户（需要真实数据库 + 已导入迁移）
# --------------------------------------------------------------------------- #

APPID = "wx1ca87185956d0071"


async def test_resolve_creates_account_with_role_and_binding(db_session):
    from sqlalchemy import select

    from app.models.permission import Role, UserRoleRelation
    from app.models.user import User
    from app.models.wechat_binding import WechatBinding
    from app.services.wechat_miniprogram_service import resolve_or_create_user

    openid = "oTestOpenid0000000000000001"

    result = await resolve_or_create_user(openid=openid, appid=APPID, db=db_session)

    assert result["is_new"] is True
    assert result["user_name"].startswith("wx_")

    user = (
        await db_session.execute(select(User).where(User.id == result["user_id"]))
    ).scalar_one()
    assert user.status == 1
    assert user.password_hash is None, "小程序账号不应有密码"
    assert user.role == "user"

    role = (
        await db_session.execute(select(Role).where(Role.code == "miniprogram_user"))
    ).scalar_one_or_none()
    if role is not None:
        relation = (
            await db_session.execute(
                select(UserRoleRelation).where(
                    UserRoleRelation.user_id == user.id,
                    UserRoleRelation.role_id == role.id,
                )
            )
        ).scalar_one_or_none()
        assert relation is not None, "必须挂上「小程序用户」角色"

    binding = (
        await db_session.execute(
            select(WechatBinding).where(
                WechatBinding.appid == APPID, WechatBinding.openid == openid
            )
        )
    ).scalar_one()
    assert binding.user_id == user.id


async def test_resolve_is_idempotent_for_same_openid(db_session):
    from app.services.wechat_miniprogram_service import resolve_or_create_user

    openid = "oTestOpenid0000000000000002"

    first = await resolve_or_create_user(openid=openid, appid=APPID, db=db_session)
    second = await resolve_or_create_user(openid=openid, appid=APPID, db=db_session)

    assert first["user_id"] == second["user_id"]
    assert first["is_new"] is True
    assert second["is_new"] is False


async def test_resolve_reuses_account_across_appids_via_unionid(db_session):
    from app.services.wechat_miniprogram_service import resolve_or_create_user

    unionid = "uTestUnionid000000000001"

    first = await resolve_or_create_user(
        openid="oTestOpenid0000000000000003",
        appid="wxappidA000000001",
        unionid=unionid,
        db=db_session,
    )
    second = await resolve_or_create_user(
        openid="oTestOpenid0000000000000004",
        appid="wxappidB000000002",
        unionid=unionid,
        db=db_session,
    )

    assert second["user_id"] == first["user_id"], "同 unionid 应复用同一账号"
    assert second["is_new"] is False


async def test_resolve_rejects_invalid_openid_without_creating_account(db_session):
    from sqlalchemy import func, select

    from app.models.user import User
    from app.services.wechat_miniprogram_service import (
        MiniprogramIdentityError,
        resolve_or_create_user,
    )

    before = (await db_session.execute(select(func.count()).select_from(User))).scalar_one()

    with pytest.raises(MiniprogramIdentityError):
        await resolve_or_create_user(openid="bad openid", appid=APPID, db=db_session)

    after = (await db_session.execute(select(func.count()).select_from(User))).scalar_one()
    assert after == before, "非法 openid 不得产生任何账号"


async def test_resolve_recovers_from_concurrent_creation_race(db_session):
    """并发建号的 IntegrityError 分支：回滚重查后按「已存在」返回，而不是抛错。

    真并发难以在单测里稳定构造（需要两条真实连接同时提交），因此这里用
    「_find_binding 首次返回 None」模拟对手请求已抢先建成（本请求的首次查询没看到），
    复制出与并发完全相同的失败点：绑定行插入撞 ux_wechat_binding_appid_openid。
    """
    from unittest.mock import patch

    from sqlalchemy import select

    from app.models.wechat_binding import WechatBinding
    from app.services import wechat_miniprogram_service as svc
    from app.services.wechat_miniprogram_service import resolve_or_create_user

    openid = "oTestOpenid0000000000000006"

    # 先正常建成（相当于并发中先到的那个请求）
    first = await resolve_or_create_user(openid=openid, appid=APPID, db=db_session)
    assert first["is_new"] is True

    real_find_binding = svc._find_binding
    calls = {"n": 0}

    async def _blind_first_lookup(db, appid, openid):  # noqa: ANN001
        calls["n"] += 1
        if calls["n"] == 1:
            return None  # 模拟「首次查询未命中」，迫使走建号路径
        return await real_find_binding(db, appid, openid)

    with patch.object(svc, "_find_binding", _blind_first_lookup):
        second = await resolve_or_create_user(openid=openid, appid=APPID, db=db_session)

    assert calls["n"] >= 2, "必须回滚后重查绑定"
    assert second["user_id"] == first["user_id"], "重查命中后必须复用同一账号"
    assert second["user_name"] == first["user_name"]
    assert second["is_new"] is False

    bindings = (
        await db_session.execute(
            select(WechatBinding).where(
                WechatBinding.appid == APPID, WechatBinding.openid == openid
            )
        )
    ).scalars().all()
    assert len(bindings) == 1, "(appid, openid) 仍必须只有一条绑定"
