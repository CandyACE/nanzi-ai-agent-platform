from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.orm import AsyncSessionLocal
from app.models.browser import BrowserSession
from app.schemas.browser import BrowserSnapshot, BrowserTab, BrowserToolResult
from app.services.ai.browser.browser_profile_service import BrowserProfileService
from app.services.ai.browser.browser_session_service import BrowserSessionService
from app.services.ai.browser.browser_worker import BrowserPageInfo, BrowserWorker


@dataclass
class _HumanControl:
    reason: str
    captcha: bool = False
    owner_id: str | None = None
    released: asyncio.Event = field(default_factory=asyncio.Event)


class BrowserRuntime:
    """当前应用进程内的浏览器 Worker 注册表。生产部署需保证会话粘滞到同一 Worker。"""

    def __init__(self, worker: BrowserWorker | None = None) -> None:
        self.worker = worker or BrowserWorker()
        self._snapshots: dict[str, BrowserSnapshot] = {}
        self._session_locks: dict[str, asyncio.Lock] = {}
        self._human_controls: dict[str, _HumanControl] = {}

    async def clean_idle_sessions(self, max_idle_seconds: float = 1800) -> list[str]:
        """按空闲时间自动释放过期的 Chromium 实例与内存快照。"""
        cleaned = await self.worker.clean_idle_sessions(max_idle_seconds=max_idle_seconds)
        for session_id in cleaned:
            self._snapshots.pop(session_id, None)
            self._session_locks.pop(session_id, None)
            state = self._human_controls.pop(session_id, None)
            if state is not None:
                state.released.set()
        return cleaned

    def _session_lock(self, session_id: str) -> asyncio.Lock:
        return self._session_locks.setdefault(session_id, asyncio.Lock())

    def _set_human_control_locked(
        self,
        session_id: str,
        *,
        reason: str,
        captcha: bool = False,
        owner_id: str | None = None,
    ) -> _HumanControl:
        state = self._human_controls.get(session_id)
        if state is None:
            state = _HumanControl(reason=reason, captcha=captcha, owner_id=owner_id)
            self._human_controls[session_id] = state
        else:
            state.reason = reason
            state.captcha = state.captcha or captcha
            if owner_id is not None:
                state.owner_id = owner_id
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
        owner_id: str | None = None,
    ) -> dict[str, Any]:
        async with self._session_lock(session_id):
            self._set_human_control_locked(
                session_id,
                reason=reason,
                captcha=captcha,
                owner_id=owner_id,
            )
            return self.control_state(session_id)

    async def release_human_control(
        self,
        session_id: str,
        *,
        owner_id: str | None = None,
    ) -> dict[str, Any]:
        async with self._session_lock(session_id):
            state = self._human_controls.get(session_id)
            if state is None:
                return self.control_state(session_id)
            if owner_id is not None and state.owner_id not in {None, owner_id}:
                return self.control_state(session_id)
            self._human_controls.pop(session_id, None)
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
                current_page_info = getattr(self.worker, "current_page_info", None)
                if callable(current_page_info):
                    current_info = await current_page_info(session.id)
                else:
                    current_info = None
                if current_info is not None and _same_browser_url(current_info.url, target_url):
                    info = current_info
                else:
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

    def _remember_snapshot_locked(self, session_id: str, snapshot: BrowserSnapshot) -> BrowserSnapshot:
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

    async def snapshot(self, session_id: str) -> BrowserSnapshot:
        async with self._session_lock(session_id):
            return self._remember_snapshot_locked(
                session_id,
                await self.worker.snapshot(session_id),
            )

    async def scroll(self, session_id: str, *, direction: str, amount: int) -> BrowserSnapshot:
        """执行低风险滚动并返回滚动后的新快照，供 Agent 继续使用最新 target_ref。"""
        while True:
            await self._wait_for_ai_control(session_id)
            async with self._session_lock(session_id):
                if session_id in self._human_controls:
                    continue
                snapshot = await self.worker.scroll(
                    session_id,
                    direction=direction,
                    amount=amount,
                )
                return self._remember_snapshot_locked(session_id, snapshot)

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

    async def navigate(
        self,
        session_id: str,
        url: str,
        *,
        owner_id: str | None = None,
    ) -> BrowserPageInfo:
        await self.acquire_human_control(session_id, reason="navigate", owner_id=owner_id)
        async with self._session_lock(session_id):
            self._snapshots.pop(session_id, None)
            return await self.worker.navigate(session_id, url)

    async def manual_input(
        self,
        session_id: str,
        *,
        event: str,
        payload: dict[str, Any],
        owner_id: str | None = None,
    ) -> BrowserPageInfo:
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
            self._set_human_control_locked(session_id, reason=reason, owner_id=owner_id)
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

    async def press(
        self,
        session_id: str,
        *,
        target_ref: str | None,
        snapshot_id: str | None,
        key: str,
    ) -> BrowserToolResult:
        while True:
            await self._wait_for_ai_control(session_id)
            async with self._session_lock(session_id):
                if session_id in self._human_controls:
                    continue
                snapshot = self.cached_snapshot(session_id, snapshot_id) if target_ref and snapshot_id else None
                result = await self.worker.press(
                    session_id,
                    target_ref=target_ref,
                    key=key,
                    snapshot=snapshot,
                )
                self._snapshots.pop(session_id, None)
                return result

    async def select_option(
        self,
        session_id: str,
        *,
        target_ref: str,
        snapshot_id: str,
        value: str | None,
        label: str | None,
    ) -> BrowserToolResult:
        while True:
            await self._wait_for_ai_control(session_id)
            async with self._session_lock(session_id):
                if session_id in self._human_controls:
                    continue
                result = await self.worker.select_option(
                    session_id,
                    target_ref=target_ref,
                    value=value,
                    label=label,
                    snapshot=self.cached_snapshot(session_id, snapshot_id),
                )
                self._snapshots.pop(session_id, None)
                return result

    async def hover(self, session_id: str, *, target_ref: str, snapshot_id: str) -> BrowserToolResult:
        while True:
            await self._wait_for_ai_control(session_id)
            async with self._session_lock(session_id):
                if session_id in self._human_controls:
                    continue
                result = await self.worker.hover(
                    session_id,
                    target_ref=target_ref,
                    snapshot=self.cached_snapshot(session_id, snapshot_id),
                )
                self._snapshots.pop(session_id, None)
                return result

    async def drag(
        self,
        session_id: str,
        *,
        source_ref: str,
        target_ref: str,
        snapshot_id: str,
    ) -> BrowserToolResult:
        while True:
            await self._wait_for_ai_control(session_id)
            async with self._session_lock(session_id):
                if session_id in self._human_controls:
                    continue
                result = await self.worker.drag(
                    session_id,
                    source_ref=source_ref,
                    target_ref=target_ref,
                    snapshot=self.cached_snapshot(session_id, snapshot_id),
                )
                self._snapshots.pop(session_id, None)
                return result

    async def wait_for(
        self,
        session_id: str,
        *,
        condition: str,
        value: str,
        timeout_ms: int,
    ) -> BrowserSnapshot:
        while True:
            await self._wait_for_ai_control(session_id)
            async with self._session_lock(session_id):
                if session_id in self._human_controls:
                    continue
                snapshot = await self.worker.wait_for(
                    session_id,
                    condition=condition,
                    value=value,
                    timeout_ms=timeout_ms,
                )
                return self._remember_snapshot_locked(session_id, snapshot)

    async def read_visible(self, session_id: str) -> dict[str, Any]:
        async with self._session_lock(session_id):
            return await self.worker.read_visible(session_id)

    async def tabs(self, session_id: str) -> list[BrowserTab]:
        async with self._session_lock(session_id):
            return await self.worker.list_tabs(session_id)

    async def switch_tab(self, session_id: str, tab_id: str) -> BrowserToolResult:
        while True:
            await self._wait_for_ai_control(session_id)
            async with self._session_lock(session_id):
                if session_id in self._human_controls:
                    continue
                info = await self.worker.switch_tab(session_id, tab_id)
                self._snapshots.pop(session_id, None)
                return BrowserToolResult(
                    session_id=session_id,
                    action="switch_tab",
                    url=info.url,
                    title=info.title,
                )

    async def close_tab(self, session_id: str, tab_id: str) -> BrowserToolResult:
        while True:
            await self._wait_for_ai_control(session_id)
            async with self._session_lock(session_id):
                if session_id in self._human_controls:
                    continue
                info = await self.worker.close_tab(session_id, tab_id)
                self._snapshots.pop(session_id, None)
                return BrowserToolResult(
                    session_id=session_id,
                    action="close_tab",
                    url=info.url,
                    title=info.title,
                )

    async def navigate_history(self, session_id: str, *, action: str) -> BrowserToolResult:
        if action not in {"back", "forward", "reload"}:
            raise ValueError("历史导航动作必须是 back、forward 或 reload")
        while True:
            await self._wait_for_ai_control(session_id)
            async with self._session_lock(session_id):
                if session_id in self._human_controls:
                    continue
                if action == "reload":
                    result = await self.worker.reload(session_id)
                else:
                    result = await getattr(self.worker, f"go_{action}")(session_id)
                self._snapshots.pop(session_id, None)
                return result

    async def upload(
        self,
        session_id: str,
        *,
        target_ref: str,
        snapshot_id: str,
        file_path: str,
    ) -> BrowserToolResult:
        while True:
            await self._wait_for_ai_control(session_id)
            async with self._session_lock(session_id):
                if session_id in self._human_controls:
                    continue
                result = await self.worker.upload(
                    session_id,
                    target_ref=target_ref,
                    file_path=file_path,
                    snapshot=self.cached_snapshot(session_id, snapshot_id),
                )
                self._snapshots.pop(session_id, None)
                return result

    async def download(
        self,
        session_id: str,
        *,
        target_ref: str,
        snapshot_id: str,
    ) -> BrowserToolResult:
        while True:
            await self._wait_for_ai_control(session_id)
            async with self._session_lock(session_id):
                if session_id in self._human_controls:
                    continue
                result = await self.worker.download(
                    session_id,
                    target_ref=target_ref,
                    snapshot=self.cached_snapshot(session_id, snapshot_id),
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


def _same_browser_url(left: str | None, right: str | None) -> bool:
    """避免根地址仅因尾部斜杠差异而重复导航。"""
    left_value = str(left or "").rstrip("/")
    right_value = str(right or "").rstrip("/")
    return bool(left_value) and left_value == right_value


browser_runtime = BrowserRuntime()
