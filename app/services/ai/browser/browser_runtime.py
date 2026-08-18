from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.orm import AsyncSessionLocal
from app.models.browser import BrowserSession
from app.schemas.browser import BrowserSnapshot, BrowserToolResult
from app.services.ai.browser.browser_profile_service import BrowserProfileService
from app.services.ai.browser.browser_session_service import BrowserSessionService
from app.services.ai.browser.browser_worker import BrowserPageInfo, BrowserWorker


@dataclass
class _HumanControl:
    reason: str
    captcha: bool = False
    released: asyncio.Event = field(default_factory=asyncio.Event)


class BrowserRuntime:
    """当前应用进程内的浏览器 Worker 注册表。生产部署需保证会话粘滞到同一 Worker。"""

    def __init__(self, worker: BrowserWorker | None = None) -> None:
        self.worker = worker or BrowserWorker()
        self._snapshots: dict[str, BrowserSnapshot] = {}
        self._session_locks: dict[str, asyncio.Lock] = {}
        self._human_controls: dict[str, _HumanControl] = {}

    def _session_lock(self, session_id: str) -> asyncio.Lock:
        return self._session_locks.setdefault(session_id, asyncio.Lock())

    def _set_human_control_locked(
        self,
        session_id: str,
        *,
        reason: str,
        captcha: bool = False,
    ) -> _HumanControl:
        state = self._human_controls.get(session_id)
        if state is None:
            state = _HumanControl(reason=reason, captcha=captcha)
            self._human_controls[session_id] = state
        else:
            state.reason = reason
            state.captcha = state.captcha or captcha
        return state

    async def _wait_for_ai_control(self, session_id: str) -> None:
        while True:
            async with self._session_lock(session_id):
                state = self._human_controls.get(session_id)
                if state is None:
                    return
                released = state.released
            await released.wait()

    def control_state(self, session_id: str) -> dict[str, Any]:
        state = self._human_controls.get(session_id)
        if state is None:
            return {"owner": "ai", "reason": None, "captcha": False}
        return {"owner": "human", "reason": state.reason, "captcha": state.captcha}

    async def acquire_human_control(
        self,
        session_id: str,
        *,
        reason: str,
        captcha: bool = False,
    ) -> dict[str, Any]:
        async with self._session_lock(session_id):
            self._set_human_control_locked(
                session_id,
                reason=reason,
                captcha=captcha,
            )
            return self.control_state(session_id)

    async def release_human_control(self, session_id: str) -> dict[str, Any]:
        async with self._session_lock(session_id):
            state = self._human_controls.pop(session_id, None)
            if state is not None:
                state.released.set()
            return self.control_state(session_id)

    async def open_session(self, db: AsyncSession, session: BrowserSession) -> BrowserPageInfo:
        await self._wait_for_ai_control(session.id)
        async with self._session_lock(session.id):
            profile = await BrowserProfileService(db).get_owned(
                user_id=int(session.user_id), profile_id=session.profile_id
            )
            profile_path = await BrowserProfileService(db).profile_path(profile)
            target_url = session.current_url or "https://www.baidu.com/"
            await db.commit()

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
            db.add(session)
            await db.commit()
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
        async with self._session_lock(session_id):
            snapshot = await self.worker.snapshot(session_id)
            current_map = self._snapshots.get(session_id)
            if not isinstance(current_map, dict):
                current_map = {}
                self._snapshots[session_id] = current_map
            current_map[snapshot.snapshot_id] = snapshot
            if len(current_map) > 5:
                oldest_key = next(iter(current_map))
                current_map.pop(oldest_key, None)
            if snapshot.page_state == "captcha":
                self._set_human_control_locked(
                    session_id,
                    reason="captcha",
                    captcha=True,
                )
            else:
                state = self._human_controls.get(session_id)
                if state is not None:
                    state.captcha = False
            return snapshot

    def cached_snapshot(self, session_id: str, snapshot_id: str) -> BrowserSnapshot:
        snapshots = self._snapshots.get(session_id)
        if isinstance(snapshots, BrowserSnapshot):
            if snapshots.snapshot_id == snapshot_id:
                return snapshots
            raise ValueError("浏览器快照已过期，请先重新获取快照")
        if not isinstance(snapshots, dict) or snapshot_id not in snapshots:
            raise ValueError("浏览器快照已过期，请先重新获取快照")
        return snapshots[snapshot_id]

    def has_session(self, session_id: str) -> bool:
        return self.worker.has_session(session_id)

    async def navigate(self, session_id: str, url: str) -> BrowserPageInfo:
        await self.acquire_human_control(session_id, reason="navigate")
        async with self._session_lock(session_id):
            self._snapshots.pop(session_id, None)
            return await self.worker.navigate(session_id, url)

    async def manual_input(self, session_id: str, *, event: str, payload: dict[str, Any]) -> BrowserPageInfo:
        reason = {
            "mouse_click": "click",
            "mouse_down": "drag",
            "mouse_move": "drag",
            "mouse_up": "drag",
            "key": "input",
            "text": "input",
            "scroll": "scroll",
        }.get(event, "input")
        async with self._session_lock(session_id):
            self._set_human_control_locked(session_id, reason=reason)
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
        while True:
            await self._wait_for_ai_control(session_id)
            async with self._session_lock(session_id):
                if session_id in self._human_controls:
                    continue
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
        while True:
            await self._wait_for_ai_control(session_id)
            async with self._session_lock(session_id):
                if session_id in self._human_controls:
                    continue
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
        async with self._session_lock(session_id):
            self._snapshots.pop(session_id, None)
            state = self._human_controls.pop(session_id, None)
            if state is not None:
                state.released.set()
            await self.worker.close(session_id)

    async def shutdown(self) -> None:
        self._snapshots.clear()
        for state in self._human_controls.values():
            state.released.set()
        self._human_controls.clear()
        self._session_locks.clear()
        await self.worker.shutdown()


browser_runtime = BrowserRuntime()
