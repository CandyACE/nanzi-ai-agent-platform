from __future__ import annotations

import inspect
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from app.schemas.browser import BrowserElement, BrowserSnapshot, BrowserToolResult
from app.services.ai.browser.browser_policy import (
    BrowserActionClass,
    BrowserUrlBlocked,
    classify_browser_action,
    decide_browser_action,
    redact_browser_arguments,
    validate_browser_navigation,
    validate_browser_request,
)


class BrowserTargetStale(RuntimeError):
    """页面已经变化，调用方必须先重新获取快照。"""


class BrowserActionConfirmationRequired(PermissionError):
    """当前 BrowserSession 需要用户确认后才能执行该动作。"""


@dataclass(frozen=True)
class BrowserPageInfo:
    url: str
    title: str


@dataclass
class _BrowserHandle:
    context: Any
    page: Any
    browser: Any = None


def _default_playwright_factory():
    from playwright.async_api import async_playwright

    return async_playwright()


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


class BrowserWorker:
    """隔离管理远程 Chromium 页面，不向上层暴露 Playwright 对象。"""

    def __init__(
        self,
        *,
        playwright_factory: Callable[[], Any] | None = None,
        url_validator: Callable[[str], str] = validate_browser_navigation,
        request_validator: Callable[[str], str] = validate_browser_request,
        screenshot_dir: str | None = "data/uploads/browser",
    ) -> None:
        self._playwright_factory = playwright_factory or _default_playwright_factory
        self._url_validator = url_validator
        self._request_validator = request_validator
        self._screenshot_dir = screenshot_dir
        self._playwright = None
        self._playwright_context_manager = None
        self._handles: dict[str, _BrowserHandle] = {}
        self._snapshots: dict[str, dict[str, dict[str, Any]]] = {}

    async def _ensure_playwright(self) -> Any:
        if self._playwright is not None:
            return self._playwright
        value = self._playwright_factory()
        value = await _maybe_await(value)
        if hasattr(value, "__aenter__"):
            self._playwright_context_manager = value
            value = await value.__aenter__()
        self._playwright = value
        return value

    async def open(self, *, session_id: str, profile_path: str, url: str) -> BrowserPageInfo:
        self._url_validator(url)
        playwright = await self._ensure_playwright()
        os.makedirs(profile_path, mode=0o700, exist_ok=True)
        try:
            os.chmod(profile_path, 0o700)
        except OSError:
            # 某些受限文件系统不支持 chmod，仍由 Worker 的路径隔离继续保护。
            pass

        chromium = playwright.chromium
        launch_persistent_context = getattr(chromium, "launch_persistent_context", None)
        if launch_persistent_context is not None:
            context = await launch_persistent_context(
                user_data_dir=profile_path,
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
                viewport={"width": 1280, "height": 800},
            )
            browser = None
        else:
            browser = await chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
            )
            context = await browser.new_context(viewport={"width": 1280, "height": 800})

        await self._install_request_guard(context)
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=25000)
            final_url = str(getattr(page, "url", url) or url)
            self._url_validator(final_url)
        except Exception:
            await _maybe_await(context.close())
            if browser is not None:
                await _maybe_await(browser.close())
            raise

        self._handles[session_id] = _BrowserHandle(context=context, page=page, browser=browser)
        self._snapshots.pop(session_id, None)
        return await self._page_info(page)

    async def _page_info(self, page: Any) -> BrowserPageInfo:
        url = str(getattr(page, "url", "") or "")
        title = str(await _maybe_await(page.title()))
        return BrowserPageInfo(url=url, title=title)

    def _handle(self, session_id: str) -> _BrowserHandle:
        try:
            return self._handles[session_id]
        except KeyError as exc:
            raise RuntimeError(f"浏览器会话不存在或已关闭：{session_id}") from exc

    async def _install_request_guard(self, context: Any) -> None:
        route_method = getattr(context, "route", None)
        if not callable(route_method):
            return

        async def handle_route(route: Any) -> None:
            request = getattr(route, "request", None)
            request_url = str(getattr(request, "url", "") or "")
            if request_url:
                try:
                    self._request_validator(request_url)
                except Exception:
                    await _maybe_await(route.abort())
                    return
            await _maybe_await(route.continue_())

        await _maybe_await(route_method("**/*", handle_route))

    async def snapshot(self, session_id: str) -> BrowserSnapshot:
        handle = self._handle(session_id)
        info = await self._page_info(handle.page)
        locator = handle.page.locator("button, input, textarea, select, a")
        raw_elements = await locator.evaluate_all(
            """
            (nodes) => nodes.slice(0, 100).map((node) => ({
              role: node.getAttribute('role') || ({
                button: 'button', a: 'link', select: 'combobox', textarea: 'textbox',
                input: (node.type === 'search' ? 'searchbox' : 'textbox')
              }[node.tagName.toLowerCase()] || node.tagName.toLowerCase()),
              sensitive: node.type === 'password' || ['current-password', 'new-password', 'password'].includes(node.getAttribute('autocomplete')),
              name: node.getAttribute('aria-label') || node.getAttribute('placeholder') || node.innerText || (node.type === 'password' || ['current-password', 'new-password', 'password'].includes(node.getAttribute('autocomplete')) ? '' : (node.value || '')),
              value: (node.type === 'password' || ['current-password', 'new-password', 'password'].includes(node.getAttribute('autocomplete'))) ? '' : (node.value || ''),
              disabled: Boolean(node.disabled),
            }))
            """
        )

        snapshot_id = uuid.uuid4().hex
        elements: list[BrowserElement] = []
        target_map: dict[str, dict[str, Any]] = {}
        for index, raw in enumerate(raw_elements or [], start=1):
            item = dict(raw or {})
            ref = f"e{index}"
            sensitive = bool(item.get("sensitive", False))
            name = item.get("name")
            if sensitive and name == item.get("value"):
                name = None
            element = BrowserElement(
                ref=ref,
                role=item.get("role"),
                name=name,
                value=None if sensitive else item.get("value"),
                disabled=bool(item.get("disabled", False)),
                sensitive=sensitive,
            )
            elements.append(element)
            target_map[ref] = item
        self._snapshots[session_id] = {snapshot_id: target_map}

        screenshot_ref = await self._capture_screenshot(handle.page, session_id, snapshot_id)
        return BrowserSnapshot(
            session_id=session_id,
            snapshot_id=snapshot_id,
            url=info.url,
            title=info.title,
            screenshot_ref=screenshot_ref,
            elements=elements,
        )

    def has_session(self, session_id: str) -> bool:
        return session_id in self._handles

    async def navigate(self, session_id: str, url: str) -> BrowserPageInfo:
        handle = self._handle(session_id)
        self._url_validator(url)
        await handle.page.goto(url, wait_until="domcontentloaded", timeout=25000)
        final_url = str(getattr(handle.page, "url", url) or url)
        self._url_validator(final_url)
        self._snapshots.pop(session_id, None)
        return await self._page_info(handle.page)

    async def manual_input(self, session_id: str, *, event: str, payload: dict[str, Any]) -> BrowserPageInfo:
        """转发面板的人工接管输入；不接受任意 JS，只转发有限的浏览器输入事件。"""
        handle = self._handle(session_id)
        if event == "mouse_click":
            x = float(payload.get("x", 0))
            y = float(payload.get("y", 0))
            pages_before = {
                id(page)
                for page in list(getattr(handle.context, "pages", []) or [])
            }
            await _maybe_await(handle.page.mouse.click(x, y))
            pages_after = list(getattr(handle.context, "pages", []) or [])
            new_pages = [page for page in pages_after if id(page) not in pages_before]
            if new_pages:
                handle.page = new_pages[-1]
                popup_url = str(getattr(handle.page, "url", "") or "")
                if popup_url:
                    self._request_validator(popup_url)
            else:
                wait_for_load_state = getattr(handle.page, "wait_for_load_state", None)
                if callable(wait_for_load_state):
                    try:
                        await _maybe_await(
                            wait_for_load_state("domcontentloaded", timeout=5000)
                        )
                    except Exception:
                        # 点击可能触发长时间加载或下载；保留当前页面并继续刷新快照。
                        pass
        elif event == "key":
            key = str(payload.get("key", ""))[:40]
            if not key:
                raise ValueError("键盘事件缺少 key")
            await _maybe_await(handle.page.keyboard.press(key))
        elif event == "text":
            text = str(payload.get("text", ""))[:2000]
            await _maybe_await(handle.page.keyboard.type(text))
        elif event == "scroll":
            delta_y = float(payload.get("delta_y", 0))
            delta_y = max(-2000.0, min(delta_y, 2000.0))
            await _maybe_await(handle.page.mouse.wheel(0, delta_y))
        else:
            raise ValueError("不支持的浏览器人工输入事件")
        self._snapshots.pop(session_id, None)
        return await self._page_info(handle.page)

    async def _capture_screenshot(self, page: Any, session_id: str, snapshot_id: str) -> str | None:
        if not self._screenshot_dir:
            return None
        directory = Path(self._screenshot_dir)
        directory.mkdir(parents=True, exist_ok=True)
        safe_session_id = re.sub(r"[^A-Za-z0-9_-]", "_", session_id)[:80] or "session"
        path = directory / f"{safe_session_id}_{snapshot_id}.png"
        await page.screenshot(path=str(path), full_page=False)
        return str(path)

    def _target(self, session_id: str, snapshot: BrowserSnapshot, target_ref: str) -> dict[str, Any]:
        snapshot_map = self._snapshots.get(session_id, {}).get(snapshot.snapshot_id)
        if snapshot.session_id != session_id or not snapshot_map or target_ref not in snapshot_map:
            raise BrowserTargetStale("浏览器页面已变化，请先重新获取页面快照")
        return snapshot_map[target_ref]

    def _locator_for(self, page: Any, target: dict[str, Any]) -> Any:
        role = str(target.get("role") or "").strip()
        name = str(target.get("name") or "").strip()
        if role and name:
            return page.get_by_role(role, name=name, exact=True)
        if role:
            return page.get_by_role(role)
        raise BrowserTargetStale("目标缺少可复现的语义定位信息，请刷新页面快照")

    async def click(
        self,
        session_id: str,
        *,
        target_ref: str,
        snapshot: BrowserSnapshot,
        approval_mode: str = "guarded",
        confirmed: bool = False,
    ) -> BrowserToolResult:
        handle = self._handle(session_id)
        target = self._target(session_id, snapshot, target_ref)
        action_class: BrowserActionClass = classify_browser_action(
            role=target.get("role"), name=target.get("name")
        )
        decision = decide_browser_action(approval_mode, action_class)
        if decision.requires_confirmation and not confirmed:
            raise BrowserActionConfirmationRequired(decision.reason)
        await self._locator_for(handle.page, target).click()
        info = await self._page_info(handle.page)
        self._snapshots.pop(session_id, None)
        return BrowserToolResult(session_id=session_id, action="click", url=info.url, title=info.title)

    async def fill(
        self,
        session_id: str,
        *,
        target_ref: str,
        value: str,
        snapshot: BrowserSnapshot,
        sensitive: bool | None = None,
    ) -> BrowserToolResult:
        handle = self._handle(session_id)
        target = self._target(session_id, snapshot, target_ref)
        await self._locator_for(handle.page, target).fill(value)
        info = await self._page_info(handle.page)
        # 页面快照推断的敏感性是下限，调用方只能追加标记，不能用 False 覆盖密码字段。
        is_sensitive = bool(target.get("sensitive", False)) or bool(sensitive)
        payload = redact_browser_arguments({"value": value, "sensitive": is_sensitive})
        self._snapshots.pop(session_id, None)
        return BrowserToolResult(
            session_id=session_id,
            action="fill",
            url=info.url,
            title=info.title,
            data=payload,
        )

    async def press(
        self,
        session_id: str,
        *,
        target_ref: str,
        key: str,
        snapshot: BrowserSnapshot,
    ) -> BrowserToolResult:
        handle = self._handle(session_id)
        target = self._target(session_id, snapshot, target_ref)
        await self._locator_for(handle.page, target).press(key)
        info = await self._page_info(handle.page)
        self._snapshots.pop(session_id, None)
        return BrowserToolResult(session_id=session_id, action="press", url=info.url, title=info.title)

    async def close(self, session_id: str) -> None:
        handle = self._handles.pop(session_id, None)
        self._snapshots.pop(session_id, None)
        if handle is None:
            return
        await _maybe_await(handle.context.close())
        if handle.browser is not None:
            await _maybe_await(handle.browser.close())

    async def shutdown(self) -> None:
        for session_id in list(self._handles):
            await self.close(session_id)
        if self._playwright_context_manager is not None:
            await self._playwright_context_manager.__aexit__(None, None, None)
        self._playwright = None
        self._playwright_context_manager = None
