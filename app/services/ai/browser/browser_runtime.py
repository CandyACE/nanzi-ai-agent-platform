from __future__ import annotations

import asyncio
import os
import time
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

# 人工接管超时：当验证码 / 人工接管触发而无人持续操作时，AI 等待超过该阈值即抛错
# 终止并上报，避免全自动运行在无人值守下永久死锁。可通过环境变量覆盖。
HUMAN_CONTROL_TIMEOUT_SECONDS = float(
    os.environ.get("BROWSER_HUMAN_CONTROL_TIMEOUT_SECONDS", "45")
)


class BrowserHumanControlRequired(RuntimeError):
    """页面需要人工接管（如验证码）但限时内无人持续操作，AI 应终止并上报。"""


@dataclass
class _HumanControl:
    reason: str
    captcha: bool = False
    owner_id: str | None = None
    released: asyncio.Event = field(default_factory=asyncio.Event)
    held_at: float = 0.0
    last_activity: float = 0.0


class BrowserRuntime:
    """当前应用进程内的浏览器 Worker 注册表。生产部署需保证会话粘滞到同一 Worker。"""

    def __init__(self, worker: BrowserWorker | None = None) -> None:
        self.worker = worker or BrowserWorker()
        self._snapshots: dict[str, BrowserSnapshot] = {}
        self._session_locks: dict[str, asyncio.Lock] = {}
        self._human_controls: dict[str, _HumanControl] = {}
        self._ai_action_status: dict[str, dict[str, Any]] = {}
        self._event_subscribers: dict[str, set[asyncio.Queue]] = {}

    def subscribe_events(self, session_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._event_subscribers.setdefault(session_id, set()).add(queue)
        return queue

    def unsubscribe_events(self, session_id: str, queue: asyncio.Queue) -> None:
        subscribers = self._event_subscribers.get(session_id)
        if subscribers:
            subscribers.discard(queue)
            if not subscribers:
                self._event_subscribers.pop(session_id, None)

    async def broadcast_event(self, session_id: str, event_data: dict[str, Any]) -> None:
        subscribers = list(self._event_subscribers.get(session_id, []))
        for q in subscribers:
            try:
                q.put_nowait(event_data)
            except Exception:
                pass

    def get_ai_action(self, session_id: str) -> dict[str, Any] | None:
        return self._ai_action_status.get(session_id)

    async def set_ai_action(self, session_id: str, action: str, detail: str) -> None:
        data = {"action": action, "detail": detail}
        self._ai_action_status[session_id] = data
        await self.broadcast_event(session_id, {"type": "ai_action", **data})

    async def clear_ai_action(self, session_id: str) -> None:
        self._ai_action_status.pop(session_id, None)
        await self.broadcast_event(session_id, {"type": "ai_action", "action": "", "detail": ""})

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
        now = time.monotonic()
        state = self._human_controls.get(session_id)
        if state is None:
            state = _HumanControl(
                reason=reason,
                captcha=captcha,
                owner_id=owner_id,
                held_at=now,
                last_activity=now,
            )
            self._human_controls[session_id] = state
        else:
            state.reason = reason
            state.captcha = state.captcha or captcha
            # 每次人工互动（手动输入、重新获取接管）都会刷新接管计时，
            # 使正在持续处理的人工不会被误判为超时放弃。
            state.last_activity = now
            if owner_id is not None:
                state.owner_id = owner_id
        return state

    async def _wait_for_ai_control(self, session_id: str, timeout_ms: int | None = None) -> None:
        """等待 AI 获得页面控制权。

        若页面正被人工接管（验证码 / 手动输入），且超过 ``timeout_ms`` 内无人持续操作，
        则抛出 :class:`BrowserHumanControlRequired`，让 AI 停止而非永久挂起。
        """
        timeout_s = (timeout_ms or 0) / 1000 if timeout_ms else HUMAN_CONTROL_TIMEOUT_SECONDS
        while True:
            async with self._session_lock(session_id):
                state = self._human_controls.get(session_id)
                if state is None:
                    return
                released = state.released
                last_activity = state.last_activity
                reason = state.reason
            if timeout_s > 0:
                elapsed_s = time.monotonic() - last_activity
                if elapsed_s >= timeout_s:
                    raise BrowserHumanControlRequired(
                        "页面需要人工接管（原因：{}，人工在 {} 秒内未持续操作）。"
                        "AI 未能获得控制权，请人工处理或结束任务。".format(reason, int(elapsed_s))
                    )
            try:
                await asyncio.wait_for(
                    released.wait(),
                    timeout=None if timeout_s <= 0 else max(0.2, timeout_s - 0.0),
                )
            except asyncio.TimeoutError:
                # 超时后回到循环头重新评估 last_activity，避免在释放与竞争间的漏检。
                continue

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
        await self.set_ai_action(session_id, "scrolling", f"正在{'向下' if direction == 'down' else '向上'}滚动页面")
        try:
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
        finally:
            await self.clear_ai_action(session_id)

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

    async def go_back(
        self,
        session_id: str,
        *,
        owner_id: str | None = None,
    ) -> BrowserToolResult:
        await self.acquire_human_control(session_id, reason="navigate", owner_id=owner_id)
        async with self._session_lock(session_id):
            self._snapshots.pop(session_id, None)
            return await self.worker.go_back(session_id)

    async def go_forward(
        self,
        session_id: str,
        *,
        owner_id: str | None = None,
    ) -> BrowserToolResult:
        await self.acquire_human_control(session_id, reason="navigate", owner_id=owner_id)
        async with self._session_lock(session_id):
            self._snapshots.pop(session_id, None)
            return await self.worker.go_forward(session_id)

    async def reload(
        self,
        session_id: str,
        *,
        owner_id: str | None = None,
    ) -> BrowserToolResult:
        await self.acquire_human_control(session_id, reason="navigate", owner_id=owner_id)
        async with self._session_lock(session_id):
            self._snapshots.pop(session_id, None)
            return await self.worker.reload(session_id)

    async def list_tabs(self, session_id: str) -> list[BrowserTab]:
        async with self._session_lock(session_id):
            return await self.worker.list_tabs(session_id)

    async def switch_tab(self, session_id: str, tab_id: str, *, owner_id: str | None = None) -> BrowserPageInfo:
        if owner_id is not None:
            await self.acquire_human_control(session_id, reason="switch_tab", owner_id=owner_id)
        else:
            while True:
                await self._wait_for_ai_control(session_id)
                async with self._session_lock(session_id):
                    if session_id in self._human_controls:
                        continue
                    break
        async with self._session_lock(session_id):
            self._snapshots.pop(session_id, None)
            return await self.worker.switch_tab(session_id, tab_id)

    async def close_tab(self, session_id: str, tab_id: str, *, owner_id: str | None = None) -> BrowserPageInfo:
        if owner_id is not None:
            await self.acquire_human_control(session_id, reason="close_tab", owner_id=owner_id)
        else:
            while True:
                await self._wait_for_ai_control(session_id)
                async with self._session_lock(session_id):
                    if session_id in self._human_controls:
                        continue
                    break
        async with self._session_lock(session_id):
            self._snapshots.pop(session_id, None)
            return await self.worker.close_tab(session_id, tab_id)

    async def close_other_tabs(self, session_id: str, tab_id: str, *, owner_id: str | None = None) -> BrowserPageInfo:
        if owner_id is not None:
            await self.acquire_human_control(session_id, reason="close_other_tabs", owner_id=owner_id)
        else:
            while True:
                await self._wait_for_ai_control(session_id)
                async with self._session_lock(session_id):
                    if session_id in self._human_controls:
                        continue
                    break
        async with self._session_lock(session_id):
            self._snapshots.pop(session_id, None)
            return await self.worker.close_other_tabs(session_id, tab_id)

    async def close_tabs_to_right(self, session_id: str, tab_id: str, *, owner_id: str | None = None) -> BrowserPageInfo:
        if owner_id is not None:
            await self.acquire_human_control(session_id, reason="close_tabs_to_right", owner_id=owner_id)
        else:
            while True:
                await self._wait_for_ai_control(session_id)
                async with self._session_lock(session_id):
                    if session_id in self._human_controls:
                        continue
                    break
        async with self._session_lock(session_id):
            self._snapshots.pop(session_id, None)
            return await self.worker.close_tabs_to_right(session_id, tab_id)

    async def close_all_tabs(self, session_id: str, *, owner_id: str | None = None) -> BrowserPageInfo:
        if owner_id is not None:
            await self.acquire_human_control(session_id, reason="close_all_tabs", owner_id=owner_id)
        else:
            while True:
                await self._wait_for_ai_control(session_id)
                async with self._session_lock(session_id):
                    if session_id in self._human_controls:
                        continue
                    break
        async with self._session_lock(session_id):
            self._snapshots.pop(session_id, None)
            return await self.worker.close_all_tabs(session_id)

    async def new_tab(self, session_id: str, url: str = "https://www.baidu.com", *, owner_id: str | None = None) -> BrowserPageInfo:
        if owner_id is not None:
            await self.acquire_human_control(session_id, reason="new_tab", owner_id=owner_id)
        else:
            while True:
                await self._wait_for_ai_control(session_id)
                async with self._session_lock(session_id):
                    if session_id in self._human_controls:
                        continue
                    break
        async with self._session_lock(session_id):
            self._snapshots.pop(session_id, None)
            return await self.worker.new_tab(session_id, url)

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
        await self.set_ai_action(session_id, "clicking", f"正在点击元素 {target_ref}")
        try:
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
        finally:
            await self.clear_ai_action(session_id)

    async def fill(
        self,
        session_id: str,
        *,
        target_ref: str,
        snapshot_id: str,
        value: str,
        sensitive: bool | None,
    ) -> BrowserToolResult:
        detail = "正在输入内容…" if sensitive else f"正在输入「{value[:20]}」"
        await self.set_ai_action(session_id, "filling", detail)
        try:
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
        finally:
            await self.clear_ai_action(session_id)

    async def press(
        self,
        session_id: str,
        *,
        target_ref: str | None,
        snapshot_id: str | None,
        key: str,
    ) -> BrowserToolResult:
        await self.set_ai_action(session_id, "pressing", f"正在发送按键 {key}")
        try:
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
        finally:
            await self.clear_ai_action(session_id)

    async def select_option(
        self,
        session_id: str,
        *,
        target_ref: str,
        snapshot_id: str,
        value: str | None,
        label: str | None,
    ) -> BrowserToolResult:
        await self.set_ai_action(session_id, "selecting", f"正在选择选项 {label or value}")
        try:
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
        finally:
            await self.clear_ai_action(session_id)

    async def hover(self, session_id: str, *, target_ref: str, snapshot_id: str) -> BrowserToolResult:
        await self.set_ai_action(session_id, "hovering", f"正在悬停元素 {target_ref}")
        try:
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
        finally:
            await self.clear_ai_action(session_id)

    async def drag(
        self,
        session_id: str,
        *,
        source_ref: str,
        target_ref: str,
        snapshot_id: str,
    ) -> BrowserToolResult:
        await self.set_ai_action(session_id, "dragging", f"正在拖拽元素 {source_ref} -> {target_ref}")
        try:
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
        finally:
            await self.clear_ai_action(session_id)

    async def slider_drag(
        self,
        session_id: str,
        *,
        source_ref: str,
        snapshot_id: str,
        distance_px: int | None = None,
        gap_target_ref: str | None = None,
    ) -> BrowserToolResult:
        await self.set_ai_action(session_id, "dragging", f"正在拖拽滑块验证码 {source_ref}")
        try:
            while True:
                await self._wait_for_ai_control(session_id)
                async with self._session_lock(session_id):
                    if session_id in self._human_controls:
                        continue
                    result = await self.worker.slider_drag(
                        session_id,
                        source_ref=source_ref,
                        snapshot=self.cached_snapshot(session_id, snapshot_id),
                        distance_px=distance_px,
                        gap_target_ref=gap_target_ref,
                    )
                    self._snapshots.pop(session_id, None)
                    return result
        finally:
            await self.clear_ai_action(session_id)

    async def wait_for(
        self,
        session_id: str,
        *,
        condition: str = "ready",
        value: str = "",
        target_ref: str | None = None,
        snapshot_id: str | None = None,
        timeout_ms: int = 5000,
    ) -> BrowserSnapshot:
        await self.set_ai_action(session_id, "waiting", "正在等待页面加载完成…")
        try:
            while True:
                await self._wait_for_ai_control(session_id, timeout_ms=timeout_ms)
                async with self._session_lock(session_id):
                    if session_id in self._human_controls:
                        continue
                    snapshot = (
                        self.cached_snapshot(session_id, snapshot_id)
                        if target_ref and snapshot_id
                        else None
                    )
                    result_snapshot = await self.worker.wait_for(
                        session_id,
                        condition=condition,
                        value=value,
                        target_ref=target_ref,
                        snapshot=snapshot,
                        timeout_ms=timeout_ms,
                    )
                    return self._remember_snapshot_locked(session_id, result_snapshot)
        finally:
            await self.clear_ai_action(session_id)

    async def read_visible(self, session_id: str) -> dict[str, Any]:
        async with self._session_lock(session_id):
            return await self.worker.read_visible(session_id)

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

    async def export_pdf(
        self,
        session_id: str,
        *,
        filename: str | None = None,
        print_background: bool = True,
    ) -> BrowserToolResult:
        await self.set_ai_action(session_id, "exporting_pdf", "AI 正在导出网页 PDF 文件")
        try:
            while True:
                await self._wait_for_ai_control(session_id)
                async with self._session_lock(session_id):
                    if session_id in self._human_controls:
                        continue
                    return await self.worker.export_pdf(
                        session_id,
                        filename=filename,
                        print_background=print_background,
                    )
        finally:
            await self.clear_ai_action(session_id)

    async def extract_table(
        self,
        session_id: str,
        *,
        selector: str | None = None,
        max_rows: int = 50,
    ) -> BrowserToolResult:
        await self.set_ai_action(session_id, "extracting_table", "AI 正在提取结构化表格数据")
        try:
            while True:
                await self._wait_for_ai_control(session_id)
                async with self._session_lock(session_id):
                    if session_id in self._human_controls:
                        continue
                    return await self.worker.extract_table(
                        session_id,
                        selector=selector,
                        max_rows=max_rows,
                    )
        finally:
            await self.clear_ai_action(session_id)

    async def handle_dialog(
        self,
        session_id: str,
        *,
        action: str = "accept",
        prompt_text: str | None = None,
    ) -> BrowserToolResult:
        async with self._session_lock(session_id):
            return await self.worker.handle_dialog(
                session_id,
                action=action,
                prompt_text=prompt_text,
            )

    async def execute_js(
        self,
        session_id: str,
        *,
        script: str,
    ) -> BrowserToolResult:
        await self.set_ai_action(session_id, "executing_js", "AI 正在执行页面脚本")
        try:
            while True:
                await self._wait_for_ai_control(session_id)
                async with self._session_lock(session_id):
                    if session_id in self._human_controls:
                        continue
                    result = await self.worker.execute_js(session_id, script=script)
                    self._snapshots.pop(session_id, None)
                    return result
        finally:
            await self.clear_ai_action(session_id)

    async def check_auth(self, session_id: str) -> BrowserToolResult:
        async with self._session_lock(session_id):
            return await self.worker.check_auth(session_id)

    async def get_network_logs(
        self,
        session_id: str,
        *,
        filter_url: str | None = None,
        limit: int = 20,
    ) -> BrowserToolResult:
        async with self._session_lock(session_id):
            return await self.worker.get_network_logs(
                session_id,
                filter_url=filter_url,
                limit=limit,
            )

    async def get_cookies(
        self,
        session_id: str,
        *,
        urls: list[str] | None = None,
    ) -> BrowserToolResult:
        async with self._session_lock(session_id):
            return await self.worker.get_cookies(session_id, urls=urls)

    async def set_cookies(
        self,
        session_id: str,
        *,
        cookies: list[dict[str, Any]],
    ) -> BrowserToolResult:
        async with self._session_lock(session_id):
            return await self.worker.set_cookies(session_id, cookies=cookies)

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
