"""微信小程序微端服务：按 openid 解析或创建平台账号，并派生会话实例标识。

设计要点见 docs/superpowers/specs/2026-10-15-miniprogram-embedchat-design.md：
- openid 由小程序云函数用 cloud.getWXContext() 取得，平台不自行调用 code2session；
- 身份映射落在独立绑定表 ai_agent_wechat_bindings，不写 ai_agent_users.extra_data；
- 自动开户只挂空角色「小程序用户」，不授予任何 api: 权限。
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.permission import Role, UserRoleRelation
from app.models.user import USER_STATUS_ENABLED, User
from app.models.wechat_binding import WechatBinding
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)

MINIPROGRAM_ROLE_CODE = "miniprogram_user"
MINIPROGRAM_USER_REAL_NAME = "微信用户"

# 微信 openid 典型为 28 位 [A-Za-z0-9_-]；放宽到 16~64 位以兼容未知变化
_OPENID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{16,64}$")


class MiniprogramIdentityError(ValueError):
    """openid / appid 等外部入参不合法。"""


def is_valid_openid(openid: Optional[str]) -> bool:
    """校验 openid 形态。非法值必须在入库前拦掉。"""
    return bool(openid) and bool(_OPENID_PATTERN.match(openid))


def _digest16(openid: str) -> str:
    return hashlib.sha256(openid.encode("utf-8")).hexdigest()[:16]


def derive_user_name(openid: str) -> str:
    """按 openid 确定性派生账号名。

    后台 UpdateUserRequest 不含 user_name（账号名建后不可改），因此必须自 openid
    派生以保证同一微信每次都命中同一账号名。仅在「建号」路径使用——改名后的
    二次识别走绑定表，不依赖本函数。
    """
    return f"wx_{_digest16(openid)}"


def derive_instance_id(openid: str) -> str:
    """按 openid 派生前端会话实例标识。

    该值决定 EmbedChat 的会话分桶与本地存储键（conversationStorageKey /
    EMBED_SESSION_STORAGE_PREFIX），必须逐用户隔离：写死会让所有微信用户共用一个分桶。
    """
    return f"wx_{_digest16(openid)}"


async def _find_binding(db: AsyncSession, appid: str, openid: str) -> Optional[WechatBinding]:
    stmt = select(WechatBinding).where(
        WechatBinding.appid == appid, WechatBinding.openid == openid
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def _find_binding_by_unionid(db: AsyncSession, unionid: str) -> Optional[WechatBinding]:
    stmt = select(WechatBinding).where(WechatBinding.unionid == unionid).limit(1)
    return (await db.execute(stmt)).scalar_one_or_none()


async def _find_user_by_name(db: AsyncSession, user_name: str) -> Optional[User]:
    stmt = select(User).where(User.user_name == user_name)
    return (await db.execute(stmt)).scalar_one_or_none()


async def _attach_miniprogram_role(db: AsyncSession, user_id: int) -> None:
    """挂上「小程序用户」角色；角色不存在时告警但不阻断开户。"""
    role = (
        await db.execute(select(Role).where(Role.code == MINIPROGRAM_ROLE_CODE))
    ).scalar_one_or_none()
    if role is None:
        logger.warning(
            "角色 %s 不存在，已跳过角色绑定（迁移 V171/V72 是否已导入？）",
            MINIPROGRAM_ROLE_CODE,
        )
        return

    existing = (
        await db.execute(
            select(UserRoleRelation).where(
                UserRoleRelation.user_id == user_id,
                UserRoleRelation.role_id == role.id,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(UserRoleRelation(user_id=user_id, role_id=role.id))


async def resolve_or_create_user(
    openid: str,
    appid: str,
    db: AsyncSession,
    unionid: Optional[str] = None,
) -> Dict[str, Any]:
    """按 (appid, openid) 解析账号；未命中回退 unionid；仍未命中则建号。

    返回 {"user_id": int, "user_name": str, "is_new": bool}
    """
    if not is_valid_openid(openid):
        raise MiniprogramIdentityError("openid 缺失或格式非法")
    if not appid:
        raise MiniprogramIdentityError("appid 缺失")

    binding = await _find_binding(db, appid, openid)
    matched_by_unionid = False
    if binding is None and unionid:
        binding = await _find_binding_by_unionid(db, unionid)
        matched_by_unionid = binding is not None

    if binding is not None:
        user = (
            await db.execute(select(User).where(User.id == binding.user_id))
        ).scalar_one_or_none()
        if user is None:
            raise MiniprogramIdentityError("绑定记录指向的账号不存在")
        if user.status != USER_STATUS_ENABLED:
            raise PermissionError("账号已被禁用")

        if matched_by_unionid:
            # 同一微信换应用（多小程序/公众号）：补一条新绑定行，复用同一账号
            db.add(
                WechatBinding(user_id=user.id, appid=appid, openid=openid, unionid=unionid)
            )
        binding.last_login_at = datetime.now()
        await db.commit()
        return {"user_id": user.id, "user_name": user.user_name, "is_new": False}

    # 建号。generate_api_key 会签发长期 API Key：明文必须就地丢弃，
    # 绝不返回给调用方、绝不写日志。「小程序用户」角色不得有任何 api: 权限，
    # 否则这枚 Key 会成为绕过前端的 V1 接口通道。
    #
    # IntegrityError 捕获（并发建号竞态）：派生幂等 ≠ 建号无冲突。同一微信快速双击、
    # 前端重试或云函数重投时，两个请求会派生**同一个 user_name** 并同时进入这里——
    # 一个成功，另一个撞 ai_agent_users.user_name 唯一键；若账号已由对手建好、只是
    # 绑定行同时插入，则撞 ux_wechat_binding_appid_openid。两者都抛 IntegrityError，
    # 不处理会直接 500。这里兜住：回滚后**重查绑定**，命中即按「已存在」返回。
    # 注意 AuthService.generate_api_key 内部已有针对唯一键冲突的 rollback，本层必须在
    # 它之外（更外层）兜底，且回滚后只能重查、不能重试插入。
    try:
        user_name = derive_user_name(openid)
        user = await _find_user_by_name(db, user_name)
        if user is None:
            await AuthService.generate_api_key(
                user_name=user_name,
                role="user",
                real_name=MINIPROGRAM_USER_REAL_NAME,
                status=USER_STATUS_ENABLED,
                db=db,
            )
            user = await _find_user_by_name(db, user_name)
            if user is None:
                raise RuntimeError("账号创建后无法查回")
            is_new = True
        else:
            # 账号名已存在但无绑定（例如管理员手工建过同名账号）：复用而不是报错
            is_new = False
            if user.status != USER_STATUS_ENABLED:
                raise PermissionError("账号已被禁用")

        await _attach_miniprogram_role(db, user.id)
        db.add(
            WechatBinding(
                user_id=user.id,
                appid=appid,
                openid=openid,
                unionid=unionid,
                last_login_at=datetime.now(),
            )
        )
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        # 并发对手已建成：绑定行必然可查（同一 (appid, openid) 只允许一条）
        existing = await _find_binding(db, appid, openid)
        if existing is None:
            raise
        existing_user = (
            await db.execute(select(User).where(User.id == existing.user_id))
        ).scalar_one_or_none()
        if existing_user is None:
            # 绑定行在、账号却不在：不是并发建号，交回原始错误
            raise exc
        existing.last_login_at = datetime.now()
        await db.commit()
        return {
            "user_id": existing_user.id,
            "user_name": existing_user.user_name,
            "is_new": False,
        }

    return {"user_id": user.id, "user_name": user.user_name, "is_new": is_new}


NEW_ACCOUNT_BURST_THRESHOLD = 5000


async def warn_if_new_account_burst() -> None:
    """高阈值建号熔断告警：只打日志，**绝不**阻断请求。

    这是「防雪崩」而非「风控」（spec §7.3）：云函数若因 bug 反复重试、
    或调用方被刷，会自动建出大量账号。达到阈值时告警一次，让人去看。
    刻意不做限流——云函数的出口 IP 是共享的、按调用者计数会误伤正常流量。
    """
    try:
        from app.core.redis import get_redis

        redis = await get_redis()
        if redis is None:
            return
        key = f"miniprogram:new_accounts:{datetime.now().strftime('%Y%m%d')}"
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, 172800)
        if count == NEW_ACCOUNT_BURST_THRESHOLD:
            logger.error(
                "小程序微端当日新建账号已达 %d 个，请检查云函数是否异常重试",
                NEW_ACCOUNT_BURST_THRESHOLD,
            )
    except Exception as e:  # 计数失败绝不能影响开户
        logger.warning("微端建号熔断计数失败（不影响开户）: %s", e)
