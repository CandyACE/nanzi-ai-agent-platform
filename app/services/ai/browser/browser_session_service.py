from __future__ import annotations

import asyncio
import hashlib
import secrets
import uuid
from datetime import datetime
from datetime import timedelta
from typing import Callable, ClassVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.browser import BrowserSession
from app.schemas.browser import BrowserApprovalMode
from app.services.ai.browser.browser_policy import validate_browser_navigation
from app.services.ai.browser.browser_profile_service import (
    BrowserProfileService,
)


class BrowserAccessDenied(PermissionError):
    """用户无权访问指定浏览器会话。"""


class BrowserSessionService:
    _open_locks: ClassVar[dict[tuple[int, str], asyncio.Lock]] = {}

    def __init__(
        self,
        db: AsyncSession,
        *,
        profile_root: str = "data/browser-profiles",
        url_validator: Callable[[str], str] = validate_browser_navigation,
    ) -> None:
        self.db = db
        self.url_validator = url_validator
        self.profile_service = BrowserProfileService(db, profile_root=profile_root)

    async def open_or_resume(
        self,
        *,
        user_id: int,
        conversation_id: str | None,
        url: str,
        profile_id: str | None,
    ) -> BrowserSession:
        self.url_validator(url)
        # 先按用户串行解析 Profile，再检查活动 Session，避免“默认 Profile”和显式
        # Profile ID 两条请求路径在同一进程内交叉创建两个 Chromium 会话。
        lock_key = (user_id, "__browser_open__")
        lock = self._open_locks.setdefault(lock_key, asyncio.Lock())
        async with lock:
            profile = (
                await self.profile_service.get_owned(user_id=user_id, profile_id=profile_id)
                if profile_id
                else await self.profile_service.get_or_create_default(user_id=user_id)
            )

            conditions = [
                BrowserSession.user_id == user_id,
                BrowserSession.profile_id == profile.id,
                BrowserSession.status.in_(("active", "waiting_user")),
            ]
            # 一个持久化 Profile 同时只挂载一个活动 Session，避免两个 Chromium
            # Context 并发打开同一 user_data_dir；新对话接管时复用该 Session。
            result = await self.db.execute(
                select(BrowserSession)
                .where(*conditions)
                .order_by(BrowserSession.updated_at.desc())
            )
            session = result.scalars().first()
            if session is not None:
                if conversation_id:
                    session.attached_conversation_id = conversation_id
                session.current_url = url
                session.updated_at = datetime.now()
                await self.db.flush()
                return session

            now = datetime.now()
            session = BrowserSession(
                id=str(uuid.uuid4()),
                profile_id=profile.id,
                user_id=user_id,
                attached_conversation_id=conversation_id,
                current_url=url,
                approval_mode=BrowserApprovalMode.AUTOPILOT.value,
                status="active",
                created_at=now,
                updated_at=now,
                last_seen_at=now,
            )
            self.db.add(session)
            await self.db.flush()
            return session

    async def get_owned_session(self, *, user_id: int, session_id: str) -> BrowserSession:
        result = await self.db.execute(
            select(BrowserSession).where(
                BrowserSession.id == session_id,
                BrowserSession.user_id == user_id,
            )
        )
        session = result.scalars().first()
        if session is None:
            raise BrowserAccessDenied("浏览器会话不存在或无权访问")
        return session

    async def list_owned_active(self, *, user_id: int) -> list[BrowserSession]:
        result = await self.db.execute(
            select(BrowserSession)
            .where(
                BrowserSession.user_id == user_id,
                BrowserSession.status.in_(("active", "waiting_user")),
            )
            .order_by(BrowserSession.updated_at.desc())
        )
        return list(result.scalars().all())

    async def update_state(
        self,
        *,
        user_id: int,
        session_id: str,
        url: str | None = None,
        title: str | None = None,
    ) -> BrowserSession:
        session = await self.get_owned_session(user_id=user_id, session_id=session_id)
        if url is not None:
            session.current_url = url
        if title is not None:
            session.page_title = title
        now = datetime.now()
        session.last_seen_at = now
        session.updated_at = now
        await self.db.flush()
        return session

    async def set_approval_mode(
        self,
        *,
        user_id: int,
        session_id: str,
        mode: BrowserApprovalMode,
    ) -> BrowserSession:
        session = await self.get_owned_session(user_id=user_id, session_id=session_id)
        session.approval_mode = mode.value
        session.updated_at = datetime.now()
        await self.db.flush()
        return session

    async def issue_viewer_token(
        self,
        *,
        user_id: int,
        session_id: str,
        ttl_minutes: int = 30,
    ) -> tuple[str, datetime]:
        session = await self.get_owned_session(user_id=user_id, session_id=session_id)
        expires_at = datetime.now() + timedelta(minutes=ttl_minutes)
        token = f"{int(expires_at.timestamp())}.{secrets.token_urlsafe(32)}"
        session.viewer_token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        session.updated_at = datetime.now()
        await self.db.flush()
        return token, expires_at

    async def resolve_viewer_token(self, token: str) -> BrowserSession:
        try:
            expires_at = int(str(token).split(".", 1)[0])
        except (ValueError, IndexError):
            raise BrowserAccessDenied("浏览器查看令牌无效") from None
        if expires_at <= int(datetime.now().timestamp()):
            raise BrowserAccessDenied("浏览器查看令牌已过期")
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        result = await self.db.execute(
            select(BrowserSession).where(
                BrowserSession.viewer_token_hash == token_hash,
                BrowserSession.status.in_(("active", "waiting_user")),
            )
        )
        session = result.scalars().first()
        if session is None:
            raise BrowserAccessDenied("浏览器查看令牌无效")
        return session

    async def mark_waiting_user(self, *, session_id: str, reason: str) -> BrowserSession:
        result = await self.db.execute(select(BrowserSession).where(BrowserSession.id == session_id))
        session = result.scalars().first()
        if session is None:
            raise BrowserAccessDenied("浏览器会话不存在")
        session.status = "waiting_user"
        session.updated_at = datetime.now()
        await self.db.flush()
        return session

    async def detach(self, *, user_id: int, session_id: str) -> BrowserSession:
        session = await self.get_owned_session(user_id=user_id, session_id=session_id)
        session.status = "detached"
        session.updated_at = datetime.now()
        await self.db.flush()
        return session

    async def close(self, *, user_id: int, session_id: str, destroy_profile: bool = False) -> None:
        session = await self.get_owned_session(user_id=user_id, session_id=session_id)
        session.status = "closed"
        session.updated_at = datetime.now()
        if destroy_profile:
            await self.profile_service.delete_owned(user_id=user_id, profile_id=session.profile_id)
        await self.db.flush()
