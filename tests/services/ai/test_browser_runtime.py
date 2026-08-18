import asyncio
from unittest.mock import AsyncMock

import pytest

from app.schemas.browser import BrowserSnapshot, BrowserToolResult
from app.services.ai.browser.browser_runtime import BrowserRuntime
from app.services.ai.browser.browser_worker import BrowserPageInfo


pytestmark = pytest.mark.no_infrastructure


class SerialProbeWorker:
    def __init__(self):
        self.active = 0
        self.max_active = 0
        self.navigate_started = asyncio.Event()
        self.release_navigation = asyncio.Event()
        self.snapshot_started = asyncio.Event()

    def _enter(self):
        self.active += 1
        self.max_active = max(self.max_active, self.active)

    def _exit(self):
        self.active -= 1

    def has_session(self, _session_id):
        return True

    async def shutdown(self):
        return None

    async def navigate(self, _session_id, _url):
        self._enter()
        self.navigate_started.set()
        await self.release_navigation.wait()
        self._exit()
        return BrowserPageInfo(url="https://example.com/", title="Example")

    async def snapshot(self, session_id):
        self._enter()
        self.snapshot_started.set()
        self._exit()
        return BrowserSnapshot(
            session_id=session_id,
            snapshot_id="snapshot-1",
            url="https://example.com/",
            title="Example",
        )


class ControlProbeWorker:
    def __init__(self):
        self.manual_input = AsyncMock(
            return_value=BrowserPageInfo(url="https://example.com/", title="Example")
        )
        self.click = AsyncMock(
            return_value=BrowserToolResult(
                session_id="session-1",
                action="click",
                url="https://example.com/",
                title="Example",
            )
        )
        self.fill = AsyncMock(
            return_value=BrowserToolResult(
                session_id="session-1",
                action="fill",
                url="https://example.com/",
                title="Example",
            )
        )

    def has_session(self, _session_id):
        return True

    async def shutdown(self):
        return None


@pytest.mark.asyncio
async def test_browser_runtime_serializes_navigation_and_snapshot_per_session():
    worker = SerialProbeWorker()
    runtime = BrowserRuntime(worker=worker)

    navigate_task = asyncio.create_task(runtime.navigate("session-1", "https://example.com/"))
    await worker.navigate_started.wait()
    snapshot_task = asyncio.create_task(runtime.snapshot("session-1"))
    await asyncio.sleep(0)

    assert worker.snapshot_started.is_set() is False

    worker.release_navigation.set()
    await asyncio.gather(navigate_task, snapshot_task)

    assert worker.max_active == 1


@pytest.mark.asyncio
async def test_browser_runtime_blocks_ai_until_human_releases_control():
    worker = ControlProbeWorker()
    runtime = BrowserRuntime(worker=worker)
    runtime._snapshots["session-1"] = BrowserSnapshot(
        session_id="session-1",
        snapshot_id="snapshot-1",
        url="https://example.com/",
        title="Example",
    )

    await runtime.manual_input("session-1", event="mouse_click", payload={"x": 10, "y": 10})
    assert runtime.control_state("session-1")["owner"] == "human"
    runtime._snapshots["session-1"] = BrowserSnapshot(
        session_id="session-1",
        snapshot_id="snapshot-1",
        url="https://example.com/",
        title="Example",
    )

    click_task = asyncio.create_task(
        runtime.click(
            "session-1",
            target_ref="e1",
            snapshot_id="snapshot-1",
            approval_mode="autopilot",
            confirmed=True,
        )
    )
    await asyncio.sleep(0)
    worker.click.assert_not_awaited()

    await runtime.release_human_control("session-1")
    await click_task
    worker.click.assert_awaited_once()
    assert runtime.control_state("session-1")["owner"] == "ai"


@pytest.mark.asyncio
async def test_browser_runtime_control_state_isolated_and_shutdown_clears_it():
    worker = ControlProbeWorker()
    runtime = BrowserRuntime(worker=worker)

    await runtime.manual_input("session-1", event="key", payload={"key": "Enter"})

    assert runtime.control_state("session-1")["owner"] == "human"
    assert runtime.control_state("session-2")["owner"] == "ai"

    await runtime.shutdown()

    assert runtime.control_state("session-1")["owner"] == "ai"


@pytest.mark.asyncio
async def test_browser_runtime_clears_captcha_flag_after_human_verification_completes():
    worker = ControlProbeWorker()
    worker.snapshot = AsyncMock(
        side_effect=[
            BrowserSnapshot(
                session_id="session-1",
                snapshot_id="captcha-1",
                url="https://example.com/",
                title="Verify",
                page_state="captcha",
            ),
            BrowserSnapshot(
                session_id="session-1",
                snapshot_id="ready-1",
                url="https://example.com/",
                title="Example",
                page_state="ready",
            ),
        ]
    )
    runtime = BrowserRuntime(worker=worker)

    await runtime.snapshot("session-1")
    assert runtime.control_state("session-1")["captcha"] is True

    await runtime.snapshot("session-1")

    assert runtime.control_state("session-1") == {
        "owner": "human",
        "reason": "captcha",
        "captcha": False,
    }
