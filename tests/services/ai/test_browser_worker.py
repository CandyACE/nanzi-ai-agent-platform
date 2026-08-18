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


class FakePage:
    def __init__(self):
        self.url = "about:blank"
        self.role_calls = []
        self.mouse = type("FakeMouse", (), {"click": AsyncMock(), "wheel": AsyncMock()})()
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


def fake_context_page(fake_playwright):
    return fake_playwright.chromium.context.page
