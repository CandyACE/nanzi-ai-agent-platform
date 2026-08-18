from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.browser import BrowserProfile


class BrowserProfileAccessDenied(PermissionError):
    """用户无权访问指定浏览器 Profile。"""


class BrowserProfileService:
    def __init__(self, db: AsyncSession, *, profile_root: str = "data/browser-profiles") -> None:
        self.db = db
        self.profile_root = Path(profile_root)

    async def get_or_create_default(self, *, user_id: int) -> BrowserProfile:
        result = await self.db.execute(
            select(BrowserProfile)
            .where(BrowserProfile.user_id == user_id, BrowserProfile.status == "active")
            .with_for_update()
            .order_by(BrowserProfile.last_used_at.desc(), BrowserProfile.created_at.asc())
        )
        profile = result.scalars().first()
        if profile is None:
            profile_id = str(uuid.uuid4())
            profile = BrowserProfile(
                id=profile_id,
                user_id=user_id,
                display_name="默认浏览器",
                encrypted_storage_ref=f"browser://profiles/{profile_id}",
                status="active",
                last_used_at=datetime.now(),
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            self.db.add(profile)
        else:
            profile.last_used_at = datetime.now()
            profile.updated_at = datetime.now()
        await self.db.flush()
        return profile

    async def get_owned(self, *, user_id: int, profile_id: str) -> BrowserProfile:
        result = await self.db.execute(
            select(BrowserProfile).where(
                BrowserProfile.id == profile_id,
                BrowserProfile.user_id == user_id,
                BrowserProfile.status == "active",
            )
        )
        profile = result.scalars().first()
        if profile is None:
            raise BrowserProfileAccessDenied("浏览器 Profile 不存在或无权访问")
        return profile

    async def list_owned(self, *, user_id: int) -> list[BrowserProfile]:
        result = await self.db.execute(
            select(BrowserProfile)
            .where(BrowserProfile.user_id == user_id, BrowserProfile.status == "active")
            .order_by(BrowserProfile.updated_at.desc())
        )
        return list(result.scalars().all())

    async def delete_owned(self, *, user_id: int, profile_id: str) -> None:
        profile = await self.get_owned(user_id=user_id, profile_id=profile_id)
        profile.status = "deleted"
        profile.updated_at = datetime.now()
        await self.db.flush()

    async def profile_path(self, profile: BrowserProfile) -> str:
        """返回内部 Worker 使用的路径，不通过 API 返回给用户。"""
        return str(self.profile_root / str(profile.user_id) / profile.id)
