from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.browser import BrowserProfile


def _calc_dir_size(path: str) -> int:
    """同步遍历目录树，返回占用字节数；路径不存在时返回 0。"""
    total = 0
    try:
        for dirpath, _, filenames in os.walk(path):
            for fname in filenames:
                fp = os.path.join(dirpath, fname)
                if not os.path.islink(fp):
                    try:
                        total += os.path.getsize(fp)
                    except OSError:
                        pass
    except OSError:
        pass
    return total


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
        await self.db.commit()
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

    async def list_owned(self, *, user_id: int) -> list[dict]:
        """返回当前用户所有活跃 profile，附带磁盘占用字节数（disk_size_bytes）。"""
        result = await self.db.execute(
            select(BrowserProfile)
            .where(BrowserProfile.user_id == user_id, BrowserProfile.status == "active")
            .order_by(BrowserProfile.updated_at.desc())
        )
        profiles = list(result.scalars().all())

        async def _with_size(profile: BrowserProfile) -> dict:
            path = await self.profile_path(profile)
            size = await asyncio.to_thread(_calc_dir_size, path)
            return {
                "id": profile.id,
                "display_name": profile.display_name,
                "status": profile.status,
                "last_used_at": profile.last_used_at,
                "created_at": profile.created_at,
                "updated_at": profile.updated_at,
                "disk_size_bytes": size,
            }

        return list(await asyncio.gather(*[_with_size(p) for p in profiles]))

    async def delete_owned(self, *, user_id: int, profile_id: str) -> None:
        profile = await self.get_owned(user_id=user_id, profile_id=profile_id)
        profile.status = "deleted"
        profile.updated_at = datetime.now()
        path = await self.profile_path(profile)
        await self.db.commit()
        # 清理物理磁盘目录
        if os.path.exists(path):
            try:
                import shutil
                shutil.rmtree(path, ignore_errors=True)
            except Exception:
                pass

    async def profile_path(self, profile: BrowserProfile) -> str:
        """返回内部 Worker 使用的路径，不通过 API 返回给用户。"""
        return str(self.profile_root / str(profile.user_id) / profile.id)
