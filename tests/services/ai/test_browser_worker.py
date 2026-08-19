import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.schemas.browser import BrowserSnapshot
from app.services.ai.browser.browser_worker import BrowserWorker


pytestmark = pytest.mark.no_infrastructure


class FakeLocator:
    def __init__(self, page, elements=None):
        self.page = page
        self.elements = elements or []
        self.click = AsyncMock()
        self.fill = AsyncMock()

    async def evaluate_all(self, _script):
        return self.elements


class FakeFrame:
    def __init__(self, focused_input=False):
        self.evaluate = AsyncMock(return_value=focused_input)


class FakePage:
    def __init__(self):
        self.url = "about:blank"
        self.role_calls = []
        self.mouse = type(
            "FakeMouse",
            (),
            {
                "click": AsyncMock(),
                "move": AsyncMock(),
                "down": AsyncMock(),
                "up": AsyncMock(),
                "wheel": AsyncMock(),
            },
        )()
        self.keyboard = type(
            "FakeKeyboard",
            (),
            {
                "press": AsyncMock(),
                "type": AsyncMock(),
                "insert_text": AsyncMock(),
            },
        )()
        self.frames = []
        self.wait_for_load_state = AsyncMock()
        self.locator_value = FakeLocator(
            self,
            [
                {
                    "role": "searchbox",
                    "name": "搜索",
                    "value": "",
                    "disabled": False,
                    "sensitive": False,
                },
                {
                    "role": "button",
                    "name": "百度一下",
                    "value": "",
                    "disabled": False,
                    "sensitive": False,
                },
                {
                    "role": "textbox",
                    "name": "密码",
                    "value": "should-not-leak",
                    "disabled": False,
                    "sensitive": True,
                },
            ],
        )

    async def goto(self, url, **_kwargs):
        self.url = url

    async def title(self):
        return "百度一下"

    async def evaluate(self, _script):
        return False

    def locator(self, _selector):
        return self.locator_value

    def get_by_role(self, role, name=None, exact=True):
        self.role_calls.append((role, name, exact))
        return self.locator_value

    async def screenshot(self, path, full_page=False):
        Path(path).write_bytes(b"png")


class FakeContext:
    def __init__(self):
        self.page = FakePage()
        self.pages = [self.page]
        self.close = AsyncMock()
        self.add_init_script = AsyncMock()

    async def new_page(self):
        return self.page


class FakeChromium:
    def __init__(self):
        self.context = FakeContext()
        self.launch_persistent_context = AsyncMock(return_value=self.context)


class FakePlaywright:
    def __init__(self):
        self.chromium = FakeChromium()


@pytest.mark.asyncio
async def test_worker_open_snapshot_and_semantic_click(tmp_path):
    fake_playwright = FakePlaywright()
    worker = BrowserWorker(
        playwright_factory=lambda: fake_playwright,
        url_validator=lambda url: url,
        screenshot_dir=str(tmp_path),
    )

    opened = await worker.open(
        session_id="bs-1",
        profile_path=str(tmp_path / "profile-1"),
        url="https://www.baidu.com/",
    )
    snapshot = await worker.snapshot("bs-1")
    result = await worker.click("bs-1", target_ref="e2", snapshot=snapshot)

    assert opened.url == "https://www.baidu.com/"
    assert snapshot.elements[0].ref == "e1"
    assert snapshot.elements[2].value is None
    assert snapshot.elements[2].sensitive is True
    assert result.action == "click"
    assert fake_playwright.chromium.launch_persistent_context.await_count == 1
    assert fake_context_page(fake_playwright).role_calls == [("button", "百度一下", True)]


@pytest.mark.asyncio
async def test_worker_can_click_a_recent_snapshot_after_another_snapshot_is_created(tmp_path):
    fake_playwright = FakePlaywright()
    worker = BrowserWorker(
        playwright_factory=lambda: fake_playwright,
        url_validator=lambda url: url,
        screenshot_dir=None,
    )
    await worker.open(
        session_id="bs-snapshot-history",
        profile_path=str(tmp_path / "profile-snapshot-history"),
        url="https://www.baidu.com/",
    )

    first = await worker.snapshot("bs-snapshot-history")
    await worker.snapshot("bs-snapshot-history")
    result = await worker.click(
        "bs-snapshot-history",
        target_ref="e2",
        snapshot=first,
        approval_mode="autopilot",
        confirmed=True,
    )

    assert result.action == "click"


@pytest.mark.asyncio
async def test_worker_fill_redacts_sensitive_value_from_result(tmp_path):
    fake_playwright = FakePlaywright()
    worker = BrowserWorker(
        playwright_factory=lambda: fake_playwright,
        url_validator=lambda url: url,
        screenshot_dir=None,
    )
    await worker.open(
        session_id="bs-2",
        profile_path=str(tmp_path / "profile-2"),
        url="https://example.com/",
    )
    snapshot = await worker.snapshot("bs-2")
    result = await worker.fill(
        "bs-2",
        target_ref="e1",
        value="secret",
        snapshot=snapshot,
        sensitive=True,
    )

    assert result.data["value"] == "<redacted>"
    fake_context_page(fake_playwright).locator_value.fill.assert_awaited_once_with("secret")


@pytest.mark.asyncio
async def test_worker_adopts_new_tab_after_manual_mouse_click(tmp_path):
    fake_playwright = FakePlaywright()
    worker = BrowserWorker(
        playwright_factory=lambda: fake_playwright,
        url_validator=lambda url: url,
        screenshot_dir=None,
    )
    await worker.open(
        session_id="bs-popup",
        profile_path=str(tmp_path / "profile-popup"),
        url="https://www.baidu.com/",
    )

    popup = FakePage()
    popup.url = "https://image.baidu.com/i?tn=baiduimage"

    async def open_popup(*_args):
        fake_playwright.chromium.context.pages.append(popup)

    fake_context_page(fake_playwright).mouse.click.side_effect = open_popup

    info = await worker.manual_input(
        "bs-popup",
        event="mouse_click",
        payload={"x": 300, "y": 36},
    )

    assert info.url == popup.url
    assert worker._handles["bs-popup"].page is popup


@pytest.mark.asyncio
async def test_worker_adopts_delayed_new_tab_after_manual_mouse_click(tmp_path):
    fake_playwright = FakePlaywright()
    worker = BrowserWorker(
        playwright_factory=lambda: fake_playwright,
        url_validator=lambda url: url,
        screenshot_dir=None,
    )
    await worker.open(
        session_id="bs-delayed-popup",
        profile_path=str(tmp_path / "profile-delayed-popup"),
        url="https://www.baidu.com/",
    )

    popup = FakePage()
    popup.url = "https://image.baidu.com/i?tn=baiduimage"

    async def append_popup():
        await asyncio.sleep(0.06)
        fake_playwright.chromium.context.pages.append(popup)

    async def open_popup(*_args):
        asyncio.create_task(append_popup())

    fake_context_page(fake_playwright).mouse.click.side_effect = open_popup

    info = await worker.manual_input(
        "bs-delayed-popup",
        event="mouse_click",
        payload={"x": 300, "y": 36},
    )

    assert info.url == popup.url
    assert worker._handles["bs-delayed-popup"].page is popup


@pytest.mark.asyncio
async def test_worker_uses_short_wait_after_manual_click(tmp_path):
    fake_playwright = FakePlaywright()
    worker = BrowserWorker(
        playwright_factory=lambda: fake_playwright,
        url_validator=lambda url: url,
        screenshot_dir=None,
    )
    await worker.open(
        session_id="bs-click-wait",
        profile_path=str(tmp_path / "profile-click-wait"),
        url="https://example.com/",
    )

    await worker.manual_input(
        "bs-click-wait",
        event="mouse_click",
        payload={"x": 300, "y": 36},
    )

    fake_context_page(fake_playwright).wait_for_load_state.assert_awaited_once_with(
        "domcontentloaded", timeout=1500
    )


@pytest.mark.asyncio
async def test_worker_reports_when_human_click_focuses_text_input(tmp_path):
    fake_playwright = FakePlaywright()
    worker = BrowserWorker(
        playwright_factory=lambda: fake_playwright,
        url_validator=lambda url: url,
        screenshot_dir=None,
    )
    await worker.open(
        session_id="bs-focus-input",
        profile_path=str(tmp_path / "profile-focus-input"),
        url="https://example.com/",
    )
    page = fake_context_page(fake_playwright)
    page.evaluate = AsyncMock(return_value=True)

    info = await worker.manual_input(
        "bs-focus-input",
        event="mouse_click",
        payload={"x": 300, "y": 200},
    )

    assert info.focused_input is True
    page.evaluate.assert_awaited_once()


@pytest.mark.asyncio
async def test_worker_exposes_current_page_info_without_navigating(tmp_path):
    fake_playwright = FakePlaywright()
    worker = BrowserWorker(
        playwright_factory=lambda: fake_playwright,
        url_validator=lambda url: url,
        screenshot_dir=None,
    )
    await worker.open(
        session_id="bs-current-page",
        profile_path=str(tmp_path / "profile-current-page"),
        url="https://example.com/",
    )

    info = await worker.current_page_info("bs-current-page")

    assert info.url == "https://example.com/"
    assert info.title == "百度一下"


@pytest.mark.asyncio
async def test_worker_reports_text_focus_inside_accessible_iframe(tmp_path):
    fake_playwright = FakePlaywright()
    worker = BrowserWorker(
        playwright_factory=lambda: fake_playwright,
        url_validator=lambda url: url,
        screenshot_dir=None,
    )
    await worker.open(
        session_id="bs-focus-iframe",
        profile_path=str(tmp_path / "profile-focus-iframe"),
        url="https://example.com/",
    )
    page = fake_context_page(fake_playwright)
    page.evaluate = AsyncMock(return_value=False)
    frame = FakeFrame(focused_input=True)
    page.frames = [frame]

    info = await worker.manual_input(
        "bs-focus-iframe",
        event="mouse_click",
        payload={"x": 300, "y": 200},
    )

    assert info.focused_input is True
    frame.evaluate.assert_awaited_once()


@pytest.mark.asyncio
async def test_worker_does_not_report_non_input_click_as_text_focus(tmp_path):
    fake_playwright = FakePlaywright()
    worker = BrowserWorker(
        playwright_factory=lambda: fake_playwright,
        url_validator=lambda url: url,
        screenshot_dir=None,
    )
    await worker.open(
        session_id="bs-focus-button",
        profile_path=str(tmp_path / "profile-focus-button"),
        url="https://example.com/",
    )

    info = await worker.manual_input(
        "bs-focus-button",
        event="mouse_click",
        payload={"x": 300, "y": 36},
    )

    assert info.focused_input is False


@pytest.mark.asyncio
async def test_worker_forwards_human_drag_pointer_events(tmp_path):
    fake_playwright = FakePlaywright()
    worker = BrowserWorker(
        playwright_factory=lambda: fake_playwright,
        url_validator=lambda url: url,
        screenshot_dir=None,
    )
    await worker.open(
        session_id="bs-drag",
        profile_path=str(tmp_path / "profile-drag"),
        url="https://example.com/",
    )
    page = fake_context_page(fake_playwright)

    await worker.manual_input("bs-drag", event="mouse_down", payload={"x": 100, "y": 200})
    await worker.manual_input("bs-drag", event="mouse_move", payload={"x": 180, "y": 200})
    await worker.manual_input("bs-drag", event="mouse_up", payload={"x": 180, "y": 200})

    page.mouse.move.assert_any_await(100, 200)
    page.mouse.move.assert_any_await(180, 200)
    page.mouse.down.assert_awaited_once_with()
    page.mouse.up.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_worker_inserts_human_text_without_key_by_key_ime_events(tmp_path):
    fake_playwright = FakePlaywright()
    worker = BrowserWorker(
        playwright_factory=lambda: fake_playwright,
        url_validator=lambda url: url,
        screenshot_dir=None,
    )
    await worker.open(
        session_id="bs-text",
        profile_path=str(tmp_path / "profile-text"),
        url="https://example.com/",
    )
    page = fake_context_page(fake_playwright)

    await worker.manual_input(
        "bs-text",
        event="text",
        payload={"text": "中文搜索"},
    )

    page.keyboard.insert_text.assert_awaited_once_with("中文搜索")
    page.keyboard.type.assert_not_awaited()


@pytest.mark.asyncio
async def test_worker_detects_explicit_captcha_page_without_matching_generic_verify_copy(tmp_path):
    fake_playwright = FakePlaywright()
    worker = BrowserWorker(
        playwright_factory=lambda: fake_playwright,
        url_validator=lambda url: url,
        screenshot_dir=None,
    )
    await worker.open(
        session_id="bs-captcha",
        profile_path=str(tmp_path / "profile-captcha"),
        url="https://example.com/",
    )
    page = fake_context_page(fake_playwright)
    page.evaluate = AsyncMock(return_value={"matched": True, "reason": "滑块验证"})

    snapshot = await worker.snapshot("bs-captcha")

    assert snapshot.page_state == "captcha"


@pytest.mark.asyncio
async def test_worker_retries_snapshot_after_navigation_context_is_destroyed(tmp_path):
    fake_playwright = FakePlaywright()
    worker = BrowserWorker(
        playwright_factory=lambda: fake_playwright,
        url_validator=lambda url: url,
        screenshot_dir=None,
    )
    await worker.open(
        session_id="bs-snapshot-retry",
        profile_path=str(tmp_path / "profile-snapshot-retry"),
        url="https://example.com/",
    )
    locator = fake_context_page(fake_playwright).locator_value
    locator.evaluate_all = AsyncMock(
        side_effect=[
            RuntimeError("Execution context was destroyed, most likely because of a navigation"),
            [],
        ]
    )

    snapshot = await worker.snapshot("bs-snapshot-retry")

    assert snapshot.url == "https://example.com/"
    assert locator.evaluate_all.await_count == 2


@pytest.mark.asyncio
async def test_worker_returns_current_page_after_navigation_timeout(tmp_path):
    fake_playwright = FakePlaywright()
    worker = BrowserWorker(
        playwright_factory=lambda: fake_playwright,
        url_validator=lambda url: url,
        screenshot_dir=None,
    )
    await worker.open(
        session_id="bs-navigation-timeout",
        profile_path=str(tmp_path / "profile-navigation-timeout"),
        url="https://www.baidu.com/",
    )
    page = fake_context_page(fake_playwright)

    async def goto_with_timeout(url, **_kwargs):
        page.url = url
        raise TimeoutError("Page.goto: Timeout 25000ms exceeded")

    page.goto = goto_with_timeout

    info = await worker.navigate("bs-navigation-timeout", "https://www.baidu.com/s?wd=有孚")

    assert info.url == "https://www.baidu.com/s?wd=有孚"


@pytest.mark.asyncio
async def test_worker_cannot_override_snapshot_sensitive_flag(tmp_path):
    fake_playwright = FakePlaywright()
    worker = BrowserWorker(
        playwright_factory=lambda: fake_playwright,
        url_validator=lambda url: url,
        screenshot_dir=None,
    )
    await worker.open(
        session_id="bs-3",
        profile_path=str(tmp_path / "profile-3"),
        url="https://example.com/",
    )
    snapshot = await worker.snapshot("bs-3")
    result = await worker.fill(
        "bs-3",
        target_ref="e3",
        value="secret",
        snapshot=snapshot,
        sensitive=False,
    )

    assert result.data["value"] == "<redacted>"


@pytest.mark.asyncio
async def test_worker_open_applies_stealth_anti_bot_options_and_init_script(tmp_path):
    fake_playwright = FakePlaywright()
    worker = BrowserWorker(
        playwright_factory=lambda: fake_playwright,
        url_validator=lambda url: url,
        screenshot_dir=None,
    )
    await worker.open(
        session_id="bs-stealth",
        profile_path=str(tmp_path / "profile-stealth"),
        url="https://example.com/",
    )

    launch_mock = fake_playwright.chromium.launch_persistent_context
    assert launch_mock.await_count == 1
    _, kwargs = launch_mock.call_args
    assert "--disable-blink-features=AutomationControlled" in kwargs["args"]
    assert "Mozilla/5.0" in kwargs["user_agent"]
    assert "HeadlessChrome" not in kwargs["user_agent"]
    assert kwargs["locale"] == "zh-CN"
    assert kwargs["timezone_id"] == "Asia/Shanghai"

    context = fake_playwright.chromium.context
    assert context.add_init_script.await_count == 1
    injected_script = context.add_init_script.call_args[0][0]
    assert "webdriver" in injected_script
    assert "window.chrome" in injected_script


def fake_context_page(fake_playwright):
    return fake_playwright.chromium.context.page
