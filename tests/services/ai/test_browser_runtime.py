import asyncio

import pytest

from app.schemas.browser import BrowserSnapshot
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
