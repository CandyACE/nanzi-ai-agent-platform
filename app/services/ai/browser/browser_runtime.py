from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.orm import AsyncSessionLocal
from app.models.browser import BrowserSession
from app.schemas.browser import BrowserSnapshot, BrowserToolResult
from app.services.ai.browser.browser_profile_service import BrowserProfileService
from app.services.ai.browser.browser_session_service import BrowserSessionService
from app.services.ai.browser.browser_worker import BrowserPageInfo, BrowserWorker


class BrowserRuntime:
    """当前应用进程内的浏览器 Worker 注册表。生产部署需保证会话粘滞到同一 Worker。"""

    def __init__(self, worker: BrowserWorker | None = None) -> None:
        self.worker = worker or BrowserWorker()
        self._snapshots: dict[str, BrowserSnapshot] = {}

    async def open_session(self, db: AsyncSession, session: BrowserSession) -> BrowserPageInfo:
        profile = await BrowserProfileService(db).get_owned(
            user_id=int(session.user_id), profile_id=session.profile_id
        )
        profile_path = await BrowserProfileService(db).profile_path(profile)
        target_url = session.current_url or "https://www.baidu.com/"
        if self.worker.has_session(session.id):
            info = await self.worker.navigate(session.id, target_url)
        else:
            info = await self.worker.open(
                session_id=session.id,
                profile_path=profile_path,
                url=target_url,
            )
        session.current_url = info.url
        session.page_title = info.title
        session.last_seen_at = datetime.now()
        session.updated_at = datetime.now()
        await db.flush()
        return info

    async def open_for_user(
        self,
        *,
        user_id: int,
        conversation_id: str | None,
        url: str,
        profile_id: str | None,
    ) -> BrowserSession:
        async with AsyncSessionLocal() as db:
            service = BrowserSessionService(db)
            session = await service.open_or_resume(
                user_id=user_id,
                conversation_id=conversation_id,
                url=url,
                profile_id=profile_id,
            )
            await self.open_session(db, session)
            await db.commit()
            return session

    async def snapshot(self, session_id: str) -> BrowserSnapshot:
        snapshot = await self.worker.snapshot(session_id)
        self._snapshots[session_id] = snapshot
        return snapshot

    def cached_snapshot(self, session_id: str, snapshot_id: str) -> BrowserSnapshot:
        snapshot = self._snapshots.get(session_id)
        if snapshot is None or snapshot.snapshot_id != snapshot_id:
            raise ValueError("浏览器快照已过期，请先重新获取快照")
        return snapshot

    def has_session(self, session_id: str) -> bool:
        return self.worker.has_session(session_id)

    async def navigate(self, session_id: str, url: str) -> BrowserPageInfo:
        self._snapshots.pop(session_id, None)
        return await self.worker.navigate(session_id, url)

    async def manual_input(self, session_id: str, *, event: str, payload: dict[str, Any]) -> BrowserPageInfo:
        self._snapshots.pop(session_id, None)
        return await self.worker.manual_input(session_id, event=event, payload=payload)

    async def click(
        self,
        session_id: str,
        *,
        target_ref: str,
        snapshot_id: str,
        approval_mode: str,
        confirmed: bool,
    ) -> BrowserToolResult:
        snapshot = self.cached_snapshot(session_id, snapshot_id)
        result = await self.worker.click(
            session_id,
            target_ref=target_ref,
            snapshot=snapshot,
            approval_mode=approval_mode,
            confirmed=confirmed,
        )
        self._snapshots.pop(session_id, None)
        return result

    async def fill(
        self,
        session_id: str,
        *,
        target_ref: str,
        snapshot_id: str,
        value: str,
        sensitive: bool | None,
    ) -> BrowserToolResult:
        snapshot = self.cached_snapshot(session_id, snapshot_id)
        result = await self.worker.fill(
            session_id,
            target_ref=target_ref,
            value=value,
            snapshot=snapshot,
            sensitive=sensitive,
        )
        self._snapshots.pop(session_id, None)
        return result

    async def close(self, session_id: str) -> None:
        self._snapshots.pop(session_id, None)
        await self.worker.close(session_id)

    async def shutdown(self) -> None:
        self._snapshots.clear()
        await self.worker.shutdown()


browser_runtime = BrowserRuntime()
