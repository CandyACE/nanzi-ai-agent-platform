from __future__ import annotations

import asyncio
import inspect
import os
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from app.schemas.browser import BrowserElement, BrowserSnapshot, BrowserTab, BrowserToolResult
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


class BrowserWaitTimeout(TimeoutError):
    """浏览器页面在限定时间内没有达到等待条件。"""


class BrowserActionConfirmationRequired(PermissionError):
    """当前 BrowserSession 需要用户确认后才能执行该动作。"""


@dataclass(frozen=True)
class BrowserPageInfo:
    url: str
    title: str
    focused_input: bool = False


DEFAULT_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

CHROMIUM_LAUNCH_ARGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-blink-features=AutomationControlled",
    "--disable-infobars",
]

MANUAL_CLICK_LOAD_TIMEOUT_MS = 1500
SNAPSHOT_NODE_SELECTOR = "body *"
SNAPSHOT_MAX_ELEMENTS = 120
SNAPSHOT_PAGE_TEXT_LIMIT = 6000
SNAPSHOT_VISIBLE_TEXT_LIMIT = 12000
SNAPSHOT_SETTLE_DELAY_MS = 150

STEALTH_INIT_SCRIPT = """
(() => {
    try {
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
            configurable: true,
        });
    } catch (_) {}

    try {
        if (!window.chrome) {
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {},
            };
        }
    } catch (_) {}

    try {
        Object.defineProperty(navigator, 'languages', {
            get: () => ['zh-CN', 'zh', 'en-US', 'en'],
            configurable: true,
        });
    } catch (_) {}

    try {
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
            configurable: true,
        });
    } catch (_) {}

    try {
        const originalQuery = window.navigator?.permissions?.query;
        if (typeof originalQuery === 'function') {
            window.navigator.permissions.query = (parameters) => (
                parameters && parameters.name === 'notifications'
                    ? Promise.resolve({ state: Notification.permission })
                    : originalQuery(parameters)
            );
        }
    } catch (_) {}
})();
"""


@dataclass
class _BrowserHandle:
    context: Any
    page: Any
    browser: Any = None
    tab_ids: dict[int, str] = field(default_factory=dict)
    next_tab_number: int = 1


def _default_playwright_factory():
    from playwright.async_api import async_playwright

    return async_playwright()


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _is_navigation_context_error(exc: BaseException) -> bool:
    message = str(exc)
    return "Execution context was destroyed" in message and "navigation" in message


def _is_navigation_timeout(exc: BaseException) -> bool:
    return isinstance(exc, TimeoutError) or exc.__class__.__name__ == "TimeoutError"


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

        common_context_kwargs: dict[str, Any] = {
            "viewport": {"width": 1280, "height": 800},
            "user_agent": DEFAULT_BROWSER_USER_AGENT,
            "locale": "zh-CN",
            "timezone_id": "Asia/Shanghai",
        }

        chromium = playwright.chromium
        launch_persistent_context = getattr(chromium, "launch_persistent_context", None)
        if launch_persistent_context is not None:
            context = await launch_persistent_context(
                user_data_dir=profile_path,
                headless=True,
                args=CHROMIUM_LAUNCH_ARGS,
                **common_context_kwargs,
            )
            browser = None
        else:
            browser = await chromium.launch(
                headless=True,
                args=CHROMIUM_LAUNCH_ARGS,
            )
            context = await browser.new_context(**common_context_kwargs)

        add_init_script = getattr(context, "add_init_script", None)
        if callable(add_init_script):
            await _maybe_await(add_init_script(STEALTH_INIT_SCRIPT))

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

    async def _page_info(self, page: Any, *, focused_input: bool = False) -> BrowserPageInfo:
        url = str(getattr(page, "url", "") or "")
        title = str(await _maybe_await(page.title()))
        return BrowserPageInfo(url=url, title=title, focused_input=focused_input)

    async def current_page_info(self, session_id: str) -> BrowserPageInfo:
        """读取当前页面信息，供恢复已有会话时避免无意义的重复导航。"""
        return await self._page_info(self._handle(session_id).page)

    def _tab_id(self, handle: _BrowserHandle, page: Any) -> str:
        key = id(page)
        existing = handle.tab_ids.get(key)
        if existing:
            return existing
        tab_id = f"tab-{handle.next_tab_number}"
        handle.next_tab_number += 1
        handle.tab_ids[key] = tab_id
        return tab_id

    def _pages(self, handle: _BrowserHandle) -> list[Any]:
        pages = list(getattr(handle.context, "pages", []) or [])
        if handle.page not in pages:
            pages.append(handle.page)
        for page in pages:
            self._tab_id(handle, page)
        return pages

    async def list_tabs(self, session_id: str) -> list[BrowserTab]:
        handle = self._handle(session_id)
        tabs: list[BrowserTab] = []
        for page in self._pages(handle):
            tabs.append(
                BrowserTab(
                    tab_id=self._tab_id(handle, page),
                    url=str(getattr(page, "url", "") or ""),
                    title=str(await _maybe_await(page.title())),
                    active=page is handle.page,
                )
            )
        return tabs

    async def switch_tab(self, session_id: str, tab_id: str) -> BrowserPageInfo:
        handle = self._handle(session_id)
        page = next(
            (candidate for candidate in self._pages(handle) if self._tab_id(handle, candidate) == tab_id),
            None,
        )
        if page is None:
            raise BrowserTargetStale("浏览器标签页不存在，请先获取标签页列表")
        handle.page = page
        self._snapshots.pop(session_id, None)
        return await self._page_info(page)

    async def close_tab(self, session_id: str, tab_id: str) -> BrowserPageInfo:
        handle = self._handle(session_id)
        pages = self._pages(handle)
        page = next(
            (candidate for candidate in pages if self._tab_id(handle, candidate) == tab_id),
            None,
        )
        if page is None:
            raise BrowserTargetStale("浏览器标签页不存在，请先获取标签页列表")
        if len(pages) <= 1:
            raise BrowserTargetStale("浏览器至少需要保留一个标签页")
        await _maybe_await(page.close())
        handle.tab_ids.pop(id(page), None)
        remaining = [candidate for candidate in pages if candidate is not page]
        if handle.page is page:
            handle.page = remaining[-1]
        self._snapshots.pop(session_id, None)
        return await self._page_info(handle.page)

    async def _has_focused_input(self, page: Any, *, x: float, y: float) -> bool:
        evaluate = getattr(page, "evaluate", None)
        if callable(evaluate):
            try:
                if bool(
                    await _maybe_await(
                        evaluate(
                            """
                            ({x, y}) => {
                              const isTextInput = (element) => {
                                const candidate = element?.closest?.('textarea, [contenteditable="true"], [role="textbox"], input');
                                if (!candidate) return false;
                                if (candidate.matches('textarea, [contenteditable="true"], [role="textbox"]')) return true;
                                return !['button', 'submit', 'reset', 'checkbox', 'radio', 'file', 'image', 'hidden']
                                  .includes((candidate.type || 'text').toLowerCase());
                              };
                              const target = document.elementFromPoint(x, y);
                              const active = document.activeElement;
                              return isTextInput(active) && (isTextInput(target) || target === active || !target);
                            }
                            """,
                            {"x": x, "y": y},
                        )
                    )
                ):
                    return True
            except Exception:
                pass

        # 点击 iframe 内的输入框时，主文档的 activeElement 通常只是 iframe 节点；
        # 对可访问的 frame 再检查一次当前焦点，跨域 frame 则由 Playwright 在 frame
        # 上执行，避免在页面中注入脚本或绕过站点权限。
        for frame in list(getattr(page, "frames", []) or []):
            frame_evaluate = getattr(frame, "evaluate", None)
            if not callable(frame_evaluate):
                continue
            try:
                if bool(
                    await _maybe_await(
                        frame_evaluate(
                            """
                            () => {
                              const active = document.activeElement;
                              if (!active) return false;
                              const candidate = active.closest?.('textarea, [contenteditable="true"], [role="textbox"], input');
                              if (!candidate) return false;
                              if (candidate.matches('textarea, [contenteditable="true"], [role="textbox"]')) return true;
                              return !['button', 'submit', 'reset', 'checkbox', 'radio', 'file', 'image', 'hidden']
                                .includes((candidate.type || 'text').toLowerCase());
                            }
                            """
                        )
                    )
                ):
                    return True
            except Exception:
                continue
        return False

    async def _detect_captcha(self, page: Any) -> tuple[bool, str | None]:
        evaluate = getattr(page, "evaluate", None)
        if not callable(evaluate):
            return False, None
        try:
            result = await _maybe_await(
                evaluate(
                    """
                    () => {
                      const bodyText = (document.body?.innerText || '').toLowerCase();
                      const textMarkers = [
                        '验证码', '安全验证', '人机验证', '滑块验证',
                        'captcha', 'verify-human'
                      ];
                      const hasTextMarker = textMarkers.some((marker) => bodyText.includes(marker));
                      const hasChallengeNode = Array.from(document.querySelectorAll('[id], [class]')).some((node) => {
                        const value = `${node.id || ''} ${typeof node.className === 'string' ? node.className : ''}`.toLowerCase();
                        return /captcha|geetest|nc_1|slider-verify|verify-slider/.test(value);
                      });
                      const hasChallengeFrame = Array.from(document.querySelectorAll('iframe')).some((frame) =>
                        /captcha|geetest|nc_1|slider-verify|verify-slider/.test((frame.getAttribute('src') || '').toLowerCase())
                      );
                      return {
                        matched: hasTextMarker || hasChallengeNode || hasChallengeFrame,
                        reason: hasTextMarker ? '页面要求人工完成安全验证' : '页面出现验证码控件'
                      };
                    }
                    """
                )
            )
            if not isinstance(result, dict) or not result.get("matched"):
                return False, None
            return True, str(result.get("reason") or "页面要求人工完成安全验证")
        except Exception:
            return False, None

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
        for attempt in range(2):
            try:
                return await self._snapshot_once(session_id)
            except Exception as exc:
                if attempt == 0 and _is_navigation_context_error(exc):
                    await asyncio.sleep(0.05)
                    continue
                raise

    async def _snapshot_once(self, session_id: str) -> BrowserSnapshot:
        handle = self._handle(session_id)
        info = await self._page_info(handle.page)
        captcha_detected, _captcha_reason = await self._detect_captcha(handle.page)
        page_context = await self._snapshot_page_context(handle.page)
        locator = handle.page.locator(SNAPSHOT_NODE_SELECTOR)
        raw_elements = await locator.evaluate_all(
            r"""
            (nodes) => {
              const interactiveRoles = new Set([
                'button', 'link', 'tab', 'option', 'menuitem', 'combobox',
                'checkbox', 'radio', 'switch', 'listbox'
              ]);
              const nativeRoles = {
                button: 'button', a: 'link', select: 'combobox', textarea: 'textbox',
                input: (node) => (node.type === 'search' ? 'searchbox' : 'textbox')
              };
              const isVisible = (node) => {
                const style = window.getComputedStyle(node);
                const rect = node.getBoundingClientRect();
                return style.display !== 'none' && style.visibility !== 'hidden'
                  && rect.width > 0 && rect.height > 0;
              };
              const cleanText = (value) => String(value || '')
                .replace(/\u00a0/g, ' ')
                .replace(/[ \t]+/g, ' ')
                .replace(/\s*\n\s*/g, '\n')
                .trim()
                .slice(0, 240);
              const candidates = [];
              for (let nodeIndex = 0; nodeIndex < nodes.length && candidates.length < %d; nodeIndex += 1) {
                const node = nodes[nodeIndex];
                const tagName = node.tagName.toLowerCase();
                const roleAttribute = (node.getAttribute('role') || '').trim().toLowerCase();
                const nativeRole = nativeRoles[tagName];
                const resolvedNativeRole = typeof nativeRole === 'function' ? nativeRole(node) : nativeRole;
                const inferredInteractive = !roleAttribute && !resolvedNativeRole && (
                  node.hasAttribute('onclick')
                  || (node.hasAttribute('tabindex') && Number(node.tabIndex) >= 0)
                  || node.hasAttribute('aria-haspopup')
                  || window.getComputedStyle(node).cursor === 'pointer'
                );
                const role = roleAttribute || resolvedNativeRole || (inferredInteractive ? 'button' : '');
                const candidate = Boolean(resolvedNativeRole)
                  || (roleAttribute && interactiveRoles.has(roleAttribute))
                  || inferredInteractive;
                if (!candidate || !isVisible(node)) continue;
                const sensitive = tagName === 'input'
                  && (node.type === 'password' || ['current-password', 'new-password', 'password'].includes(node.getAttribute('autocomplete')));
                const rawName = node.getAttribute('aria-label')
                  || node.getAttribute('title')
                  || node.getAttribute('placeholder')
                  || node.innerText
                  || (node.value || '');
                candidates.push({
                  role,
                  _role_source: roleAttribute ? 'explicit' : resolvedNativeRole ? 'native' : 'inferred',
                  _node_index: nodeIndex,
                  sensitive,
                  name: cleanText(rawName),
                  value: sensitive ? '' : cleanText(node.value || ''),
                  disabled: Boolean(node.disabled) || node.getAttribute('aria-disabled') === 'true',
                });
              }
              return candidates;
            }
            """
            % SNAPSHOT_MAX_ELEMENTS
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
        if session_id not in self._snapshots:
            self._snapshots[session_id] = {}
        self._snapshots[session_id][snapshot_id] = target_map
        if len(self._snapshots[session_id]) > 5:
            oldest_key = next(iter(self._snapshots[session_id]))
            self._snapshots[session_id].pop(oldest_key, None)

        screenshot_ref = await self._capture_screenshot(handle.page, session_id, snapshot_id)
        return BrowserSnapshot(
            session_id=session_id,
            snapshot_id=snapshot_id,
            tab_id=self._tab_id(handle, handle.page),
            url=info.url,
            title=info.title,
            screenshot_ref=screenshot_ref,
            elements=elements,
            page_state="captcha" if captcha_detected else "ready",
            scroll_x=page_context.get("scroll_x", 0),
            scroll_y=page_context.get("scroll_y", 0),
            viewport_width=page_context.get("viewport_width"),
            viewport_height=page_context.get("viewport_height"),
            document_width=page_context.get("document_width"),
            document_height=page_context.get("document_height"),
            page_text=page_context.get("page_text", ""),
            visible_text=page_context.get("visible_text", ""),
        )

    async def _snapshot_page_context(self, page: Any) -> dict[str, Any]:
        evaluate = getattr(page, "evaluate", None)
        if not callable(evaluate):
            return {}
        try:
            result = await _maybe_await(
                evaluate(
                    r"""
                    () => {
                      const root = document.documentElement;
                      const body = document.body;
                      const cleanText = (value) => String(value || '')
                        .replace(/\u00a0/g, ' ')
                        .replace(/[ \t]+/g, ' ')
                        .replace(/\s*\n\s*/g, '\n')
                        .replace(/\n{3,}/g, '\n\n')
                        .trim();
                      const visibleText = () => {
                        const viewportWidth = window.innerWidth || 0;
                        const viewportHeight = window.innerHeight || 0;
                        const lines = [];
                        for (const node of Array.from(body?.querySelectorAll('*') || [])) {
                          const style = window.getComputedStyle(node);
                          const rect = node.getBoundingClientRect();
                          const hasDirectText = Array.from(node.childNodes || [])
                            .some((child) => child.nodeType === Node.TEXT_NODE && String(child.textContent || '').trim());
                          if (!hasDirectText || style.display === 'none' || style.visibility === 'hidden'
                            || rect.width <= 0 || rect.height <= 0 || rect.right <= 0 || rect.bottom <= 0
                            || rect.left >= viewportWidth || rect.top >= viewportHeight) continue;
                          const text = cleanText(node.textContent || '');
                          if (text) lines.push(text);
                        }
                        return Array.from(new Set(lines)).join('\n').slice(0, %d);
                      };
                      return {
                        scroll_x: Math.round(window.scrollX || 0),
                        scroll_y: Math.round(window.scrollY || 0),
                        viewport_width: Math.round(window.innerWidth || 0),
                        viewport_height: Math.round(window.innerHeight || 0),
                        document_width: Math.max(root?.scrollWidth || 0, body?.scrollWidth || 0),
                        document_height: Math.max(root?.scrollHeight || 0, body?.scrollHeight || 0),
                        page_text: cleanText(body?.innerText || '').slice(0, %d),
                        visible_text: visibleText(),
                      };
                    }
                    """
                    % (SNAPSHOT_VISIBLE_TEXT_LIMIT, SNAPSHOT_PAGE_TEXT_LIMIT)
                )
            )
        except Exception:
            return {}
        if not isinstance(result, dict):
            return {}
        context: dict[str, Any] = {}
        for key in ("scroll_x", "scroll_y"):
            try:
                context[key] = float(result.get(key) or 0)
            except (TypeError, ValueError):
                context[key] = 0
        for key in ("viewport_width", "viewport_height", "document_width", "document_height"):
            try:
                value = result.get(key)
                context[key] = int(value) if value is not None else None
            except (TypeError, ValueError):
                context[key] = None
        context["page_text"] = str(result.get("page_text") or "")[:SNAPSHOT_PAGE_TEXT_LIMIT]
        context["visible_text"] = str(result.get("visible_text") or "")[:SNAPSHOT_VISIBLE_TEXT_LIMIT]
        return context

    def has_session(self, session_id: str) -> bool:
        return session_id in self._handles

    async def navigate(self, session_id: str, url: str) -> BrowserPageInfo:
        handle = self._handle(session_id)
        self._url_validator(url)
        previous_url = str(getattr(handle.page, "url", "") or "")
        try:
            await handle.page.goto(url, wait_until="domcontentloaded", timeout=25000)
        except Exception as exc:
            if not _is_navigation_timeout(exc):
                raise
            final_url = str(getattr(handle.page, "url", "") or "")
            if not final_url or final_url == previous_url:
                raise
            self._url_validator(final_url)
            self._snapshots.pop(session_id, None)
            return await self._page_info(handle.page)
        final_url = str(getattr(handle.page, "url", url) or url)
        self._url_validator(final_url)
        self._snapshots.pop(session_id, None)
        return await self._page_info(handle.page)

    async def scroll(self, session_id: str, *, direction: str, amount: int) -> BrowserSnapshot:
        """滚动当前页面并返回滚动后的完整语义快照。"""
        handle = self._handle(session_id)
        normalized_direction = str(direction or "down").strip().lower()
        if normalized_direction not in {"up", "down", "top", "bottom"}:
            raise ValueError("滚动方向必须是 up、down、top 或 bottom")
        normalized_amount = max(100, min(abs(int(amount or 640)), 2000))

        if normalized_direction == "top":
            await _maybe_await(handle.page.evaluate("() => window.scrollTo(0, 0)"))
        elif normalized_direction == "bottom":
            await _maybe_await(
                handle.page.evaluate(
                    "() => window.scrollTo(0, Math.max(document.body.scrollHeight, document.documentElement.scrollHeight))"
                )
            )
        else:
            delta_y = normalized_amount if normalized_direction == "down" else -normalized_amount
            await _maybe_await(handle.page.mouse.wheel(0, delta_y))

        wait_for_timeout = getattr(handle.page, "wait_for_timeout", None)
        if callable(wait_for_timeout):
            await _maybe_await(wait_for_timeout(SNAPSHOT_SETTLE_DELAY_MS))
        else:
            await asyncio.sleep(0)
        self._snapshots.pop(session_id, None)
        return await self.snapshot(session_id)

    async def wait_for(
        self,
        session_id: str,
        *,
        condition: str,
        value: str,
        timeout_ms: int = 5000,
    ) -> BrowserSnapshot:
        """等待受限页面条件满足后返回新快照，不执行任意页面脚本。"""
        handle = self._handle(session_id)
        normalized_condition = str(condition or "text").strip().lower()
        if normalized_condition not in {"text", "url", "target", "page_state"}:
            raise ValueError("等待条件必须是 text、url、target 或 page_state")
        timeout = max(100, min(int(timeout_ms or 5000), 10000))
        expected = str(value or "").strip()
        if not expected:
            raise ValueError("等待条件值不能为空")
        deadline = asyncio.get_running_loop().time() + (timeout / 1000)
        while True:
            current_url = str(getattr(handle.page, "url", "") or "")
            if normalized_condition == "url" and expected in current_url:
                return await self.snapshot(session_id)
            if normalized_condition in {"text", "target"}:
                context = await self._snapshot_page_context(handle.page)
                haystack = context.get("visible_text" if normalized_condition == "target" else "page_text", "")
                if expected.casefold() in str(haystack).casefold():
                    return await self.snapshot(session_id)
            if normalized_condition == "page_state":
                captcha, _reason = await self._detect_captcha(handle.page)
                current_state = "captcha" if captcha else "ready"
                if expected.casefold() == current_state:
                    return await self.snapshot(session_id)
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise BrowserWaitTimeout(f"等待浏览器条件超时：{normalized_condition}={expected}")
            wait_for_timeout = getattr(handle.page, "wait_for_timeout", None)
            if callable(wait_for_timeout):
                await _maybe_await(wait_for_timeout(min(250, max(1, int(remaining * 1000)))))
            else:
                await asyncio.sleep(min(0.25, remaining))

    async def read_visible(self, session_id: str) -> dict[str, Any]:
        handle = self._handle(session_id)
        page_context = await self._snapshot_page_context(handle.page)
        info = await self._page_info(handle.page)
        return {
            "session_id": session_id,
            "url": info.url,
            "title": info.title,
            "scroll_x": page_context.get("scroll_x", 0),
            "scroll_y": page_context.get("scroll_y", 0),
            "text": page_context.get("visible_text", ""),
        }

    async def press(
        self,
        session_id: str,
        *,
        target_ref: str | None,
        key: str,
        snapshot: BrowserSnapshot | None,
    ) -> BrowserToolResult:
        handle = self._handle(session_id)
        normalized_key = str(key or "").strip()[:40]
        if not normalized_key:
            raise ValueError("键盘操作缺少 key")
        if target_ref:
            if snapshot is None:
                raise BrowserTargetStale("按目标发送键盘操作需要页面快照")
            target = self._target(session_id, snapshot, target_ref)
            locator = self._locator_for(handle.page, target)
            await self._validate_inferred_target(locator, target)
            await locator.press(normalized_key)
        else:
            await _maybe_await(handle.page.keyboard.press(normalized_key))
        info = await self._page_info(handle.page)
        self._snapshots.pop(session_id, None)
        return BrowserToolResult(session_id=session_id, action="press", url=info.url, title=info.title)

    async def select_option(
        self,
        session_id: str,
        *,
        target_ref: str,
        snapshot: BrowserSnapshot,
        value: str | None,
        label: str | None = None,
    ) -> BrowserToolResult:
        handle = self._handle(session_id)
        target = self._target(session_id, snapshot, target_ref)
        locator = self._locator_for(handle.page, target)
        await self._validate_inferred_target(locator, target)
        select_option = getattr(locator, "select_option", None)
        if not callable(select_option):
            raise BrowserTargetStale("当前目标不是可选下拉框，请重新获取快照")
        options: dict[str, str] = {}
        if value:
            options["value"] = value
        elif label:
            options["label"] = label
        else:
            raise ValueError("下拉选择需要 value 或 label")
        try:
            await _maybe_await(select_option(**options))
        except Exception as exc:
            option_name = label or value
            try:
                await _maybe_await(locator.click())
                option_locator = handle.page.get_by_role("option", name=option_name, exact=True)
                await _maybe_await(option_locator.click())
            except Exception as fallback_exc:
                raise BrowserTargetStale("下拉目标无法选择该选项，请刷新页面快照") from fallback_exc
        info = await self._page_info(handle.page)
        self._snapshots.pop(session_id, None)
        return BrowserToolResult(session_id=session_id, action="select_option", url=info.url, title=info.title)

    async def hover(
        self,
        session_id: str,
        *,
        target_ref: str,
        snapshot: BrowserSnapshot,
    ) -> BrowserToolResult:
        handle = self._handle(session_id)
        target = self._target(session_id, snapshot, target_ref)
        locator = self._locator_for(handle.page, target)
        await self._validate_inferred_target(locator, target)
        await _maybe_await(locator.hover())
        info = await self._page_info(handle.page)
        self._snapshots.pop(session_id, None)
        return BrowserToolResult(session_id=session_id, action="hover", url=info.url, title=info.title)

    async def drag(
        self,
        session_id: str,
        *,
        source_ref: str,
        target_ref: str,
        snapshot: BrowserSnapshot,
    ) -> BrowserToolResult:
        handle = self._handle(session_id)
        source = self._target(session_id, snapshot, source_ref)
        target = self._target(session_id, snapshot, target_ref)
        source_locator = self._locator_for(handle.page, source)
        target_locator = self._locator_for(handle.page, target)
        await self._validate_inferred_target(source_locator, source)
        await self._validate_inferred_target(target_locator, target)
        await _maybe_await(source_locator.drag_to(target_locator))
        info = await self._page_info(handle.page)
        self._snapshots.pop(session_id, None)
        return BrowserToolResult(session_id=session_id, action="drag", url=info.url, title=info.title)

    async def upload(
        self,
        session_id: str,
        *,
        target_ref: str,
        file_path: str,
        snapshot: BrowserSnapshot,
    ) -> BrowserToolResult:
        handle = self._handle(session_id)
        source = Path(file_path).resolve()
        if not source.is_file():
            raise ValueError("待上传文件不存在")
        if source.stat().st_size > 20 * 1024 * 1024:
            raise ValueError("上传文件大小不能超过 20MB")
        target = self._target(session_id, snapshot, target_ref)
        locator = self._locator_for(handle.page, target)
        await self._validate_inferred_target(locator, target)
        set_input_files = getattr(locator, "set_input_files", None)
        if not callable(set_input_files):
            raise BrowserTargetStale("当前目标不是文件输入控件，请重新获取快照")
        await _maybe_await(set_input_files(str(source)))
        info = await self._page_info(handle.page)
        self._snapshots.pop(session_id, None)
        return BrowserToolResult(
            session_id=session_id,
            action="upload",
            url=info.url,
            title=info.title,
            data={"filename": source.name, "size": source.stat().st_size},
        )

    async def download(
        self,
        session_id: str,
        *,
        target_ref: str,
        snapshot: BrowserSnapshot,
    ) -> BrowserToolResult:
        handle = self._handle(session_id)
        target = self._target(session_id, snapshot, target_ref)
        locator = self._locator_for(handle.page, target)
        await self._validate_inferred_target(locator, target)
        expect_download = getattr(handle.page, "expect_download", None)
        if not callable(expect_download):
            raise RuntimeError("当前浏览器不支持下载捕获")
        async with expect_download(timeout=25000) as download_info:
            await _maybe_await(locator.click())
        download = await _maybe_await(download_info.value)
        path_method = getattr(download, "path", None)
        download_path = await _maybe_await(path_method()) if callable(path_method) else None
        filename = str(getattr(download, "suggested_filename", "download") or "download")
        if not download_path:
            raise RuntimeError("浏览器下载文件不可用")
        info = await self._page_info(handle.page)
        self._snapshots.pop(session_id, None)
        return BrowserToolResult(
            session_id=session_id,
            action="download",
            url=info.url,
            title=info.title,
            data={"download_path": str(download_path), "filename": Path(filename).name},
        )

    async def _history_action(self, session_id: str, action: str) -> BrowserToolResult:
        handle = self._handle(session_id)
        method = getattr(handle.page, action, None)
        if not callable(method):
            raise RuntimeError(f"浏览器不支持{action}操作")
        await _maybe_await(method(wait_until="domcontentloaded", timeout=25000))
        info = await self._page_info(handle.page)
        self._url_validator(info.url)
        self._snapshots.pop(session_id, None)
        return BrowserToolResult(session_id=session_id, action=action, url=info.url, title=info.title)

    async def go_back(self, session_id: str) -> BrowserToolResult:
        return await self._history_action(session_id, "go_back")

    async def go_forward(self, session_id: str) -> BrowserToolResult:
        return await self._history_action(session_id, "go_forward")

    async def reload(self, session_id: str) -> BrowserToolResult:
        return await self._history_action(session_id, "reload")

    async def manual_input(self, session_id: str, *, event: str, payload: dict[str, Any]) -> BrowserPageInfo:
        """转发面板的人工接管输入；不接受任意 JS，只转发有限的浏览器输入事件。"""
        handle = self._handle(session_id)
        focused_input = False
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
            if not new_pages:
                for _ in range(8):
                    await asyncio.sleep(0.05)
                    pages_after = list(getattr(handle.context, "pages", []) or [])
                    new_pages = [page for page in pages_after if id(page) not in pages_before]
                    if new_pages:
                        break
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
                            wait_for_load_state(
                                "domcontentloaded",
                                timeout=MANUAL_CLICK_LOAD_TIMEOUT_MS,
                            )
                        )
                    except Exception:
                        # 点击可能触发长时间加载或下载；保留当前页面并继续刷新快照。
                        pass
            focused_input = await self._has_focused_input(handle.page, x=x, y=y)
        elif event == "key":
            key = str(payload.get("key", ""))[:40]
            if not key:
                raise ValueError("键盘事件缺少 key")
            await _maybe_await(handle.page.keyboard.press(key))
        elif event == "text":
            text = str(payload.get("text", ""))[:2000]
            insert_text = getattr(handle.page.keyboard, "insert_text", None)
            if callable(insert_text):
                await _maybe_await(insert_text(text))
            else:
                await _maybe_await(handle.page.keyboard.type(text))
        elif event == "mouse_down":
            x = float(payload.get("x", 0))
            y = float(payload.get("y", 0))
            await _maybe_await(handle.page.mouse.move(x, y))
            await _maybe_await(handle.page.mouse.down())
        elif event == "mouse_move":
            x = float(payload.get("x", 0))
            y = float(payload.get("y", 0))
            await _maybe_await(handle.page.mouse.move(x, y))
        elif event == "mouse_up":
            x = float(payload.get("x", 0))
            y = float(payload.get("y", 0))
            await _maybe_await(handle.page.mouse.move(x, y))
            await _maybe_await(handle.page.mouse.up())
        elif event == "scroll":
            delta_y = float(payload.get("delta_y", 0))
            delta_y = max(-2000.0, min(delta_y, 2000.0))
            await _maybe_await(handle.page.mouse.wheel(0, delta_y))
        else:
            raise ValueError("不支持的浏览器人工输入事件")
        self._snapshots.pop(session_id, None)
        return await self._page_info(handle.page, focused_input=focused_input)

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
        handle = self._handle(session_id)
        if snapshot.tab_id and snapshot.tab_id != self._tab_id(handle, handle.page):
            raise BrowserTargetStale("浏览器页面已变化，请先重新获取页面快照")
        snapshot_map = self._snapshots.get(session_id, {}).get(snapshot.snapshot_id)
        if snapshot.session_id != session_id or not snapshot_map or target_ref not in snapshot_map:
            raise BrowserTargetStale("浏览器页面已变化，请先重新获取页面快照")
        return snapshot_map[target_ref]

    def _locator_for(self, page: Any, target: dict[str, Any]) -> Any:
        if target.get("_role_source") == "inferred":
            node_index = target.get("_node_index")
            if isinstance(node_index, int) and node_index >= 0:
                return page.locator(SNAPSHOT_NODE_SELECTOR).nth(node_index)
        role = str(target.get("role") or "").strip()
        name = str(target.get("name") or "").strip()
        if role and name:
            return page.get_by_role(role, name=name, exact=True)
        if role:
            return page.get_by_role(role)
        raise BrowserTargetStale("目标缺少可复现的语义定位信息，请刷新页面快照")

    async def _validate_inferred_target(self, locator: Any, target: dict[str, Any]) -> None:
        if target.get("_role_source") != "inferred":
            return
        evaluate = getattr(locator, "evaluate", None)
        if not callable(evaluate):
            return
        try:
            current = await _maybe_await(
                evaluate(
                    """
                    (node) => ({
                      name: node.getAttribute('aria-label')
                        || node.getAttribute('title')
                        || node.getAttribute('placeholder')
                        || node.innerText
                        || node.value
                        || ''
                    })
                    """
                )
            )
        except Exception as exc:
            raise BrowserTargetStale("浏览器页面已变化，请先重新获取页面快照") from exc
        expected_name = " ".join(str(target.get("name") or "").split()).casefold()
        current_name = " ".join(str((current or {}).get("name") or "").split()).casefold()
        if expected_name and current_name and expected_name not in current_name and current_name not in expected_name:
            raise BrowserTargetStale("浏览器页面已变化，请先重新获取页面快照")

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
        locator = self._locator_for(handle.page, target)
        await self._validate_inferred_target(locator, target)
        await locator.click()
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
        locator = self._locator_for(handle.page, target)
        await self._validate_inferred_target(locator, target)
        await locator.fill(value)
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
