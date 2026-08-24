import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.browser import BrowserSnapshot
from app.services.ai.browser.browser_runtime import BrowserRuntime
from app.services.ai.browser.captcha_solver import BrowserCaptchaSolver

pytestmark = pytest.mark.no_infrastructure


class DummyPage:
    def __init__(self):
        self.mouse = SimpleNamespace(
            move=AsyncMock(),
            down=AsyncMock(),
            up=AsyncMock(),
            click=AsyncMock(),
        )
        self.viewport_size = {"width": 1280, "height": 800}

    async def screenshot(self, **kwargs):
        return b"fake_jpeg_bytes"

    def locator(self, sel):
        loc = AsyncMock()
        loc.bounding_box = AsyncMock(return_value={"x": 100, "y": 200, "width": 40, "height": 40})
        loc.first = loc
        return loc


class DummyWorker:
    def __init__(self, page_state="captcha"):
        self.page = DummyPage()
        self.handle = SimpleNamespace(page=self.page)
        self._page_state = page_state
        self.snapshot_call_count = 0

    def _handle(self, session_id):
        return self.handle

    def _slider_trajectory(self, sx, sy, travel_px):
        return [(sx + travel_px * 0.5, sy, 0.01), (sx + travel_px, sy, 0.01)]

    async def _human_smooth_mouse_move(self, page, x, y, steps=10):
        await page.mouse.move(x, y)

    async def snapshot(self, session_id):
        self.snapshot_call_count += 1
        return BrowserSnapshot(
            session_id=session_id,
            snapshot_id=f"snap-{self.snapshot_call_count}",
            url="https://example.com/login",
            title="Login",
            page_state=self._page_state,
        )


@pytest.mark.asyncio
async def test_captcha_solver_slider_success():
    worker = DummyWorker(page_state="ready")  # 动作执行后变为 ready
    solver = BrowserCaptchaSolver(worker)

    mock_llm_response = SimpleNamespace(
        content=json.dumps({
            "type": "slider",
            "slider_x": 120,
            "slider_y": 220,
            "target_x": 320,
            "target_y": 220,
            "distance_px": 200,
        })
    )

    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = mock_llm_response

    with patch.object(solver, "_resolve_vision_model", AsyncMock(return_value="mock-vision-model")), \
         patch("app.services.ai.config.AgentConfigProvider.get_configured_llm", AsyncMock(return_value=mock_llm)):
        snapshot = BrowserSnapshot(
            session_id="s1",
            snapshot_id="snap-0",
            url="https://example.com/login",
            title="Login",
            page_state="captcha",
        )
        success = await solver.solve_captcha("s1", snapshot)
        assert success is True
        assert worker.page.mouse.move.called
        assert worker.page.mouse.down.called
        assert worker.page.mouse.up.called


@pytest.mark.asyncio
async def test_captcha_solver_click_sequence_success():
    worker = DummyWorker(page_state="ready")
    solver = BrowserCaptchaSolver(worker)

    mock_llm_response = SimpleNamespace(
        content=json.dumps({
            "type": "click_sequence",
            "points": [{"x": 150, "y": 250}, {"x": 280, "y": 310}],
        })
    )

    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = mock_llm_response

    with patch.object(solver, "_resolve_vision_model", AsyncMock(return_value="mock-vision-model")), \
         patch("app.services.ai.config.AgentConfigProvider.get_configured_llm", AsyncMock(return_value=mock_llm)):
        snapshot = BrowserSnapshot(
            session_id="s1",
            snapshot_id="snap-0",
            url="https://example.com/login",
            title="Login",
            page_state="captcha",
        )
        success = await solver.solve_captcha("s1", snapshot)
        assert success is True
        assert worker.page.mouse.click.call_count == 2


@pytest.mark.asyncio
async def test_captcha_solver_unsupported_returns_false():
    worker = DummyWorker(page_state="captcha")
    solver = BrowserCaptchaSolver(worker)

    mock_llm_response = SimpleNamespace(
        content=json.dumps({
            "type": "unsupported",
            "reason": "需要短信验证码",
        })
    )

    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = mock_llm_response

    with patch.object(solver, "_resolve_vision_model", AsyncMock(return_value="mock-vision-model")), \
         patch("app.services.ai.config.AgentConfigProvider.get_configured_llm", AsyncMock(return_value=mock_llm)):
        snapshot = BrowserSnapshot(
            session_id="s1",
            snapshot_id="snap-0",
            url="https://example.com/login",
            title="Login",
            page_state="captcha",
        )
        success = await solver.solve_captcha("s1", snapshot)
        assert success is False


@pytest.mark.asyncio
async def test_runtime_auto_solves_captcha_and_falls_back_to_human_control_on_failure():
    worker = DummyWorker(page_state="captcha")
    runtime = BrowserRuntime(worker=worker)

    # Mock solver solve_captcha 失败
    runtime.captcha_solver.solve_captcha = AsyncMock(return_value=False)

    snapshot = await runtime.snapshot("session-1")
    assert snapshot.page_state == "captcha"
    # 确认触发了人工接管
    control = runtime.control_state("session-1")
    assert control["owner"] == "human"
    assert control["reason"] == "captcha"
    assert control["captcha"] is True


@pytest.mark.asyncio
async def test_runtime_auto_solves_captcha_successfully():
    worker = DummyWorker(page_state="captcha")
    runtime = BrowserRuntime(worker=worker)

    # 首次触发自解算成功，worker 下一次 snapshot 变为 ready
    async def fake_solve(session_id, snapshot):
        worker._page_state = "ready"
        return True

    runtime.captcha_solver.solve_captcha = AsyncMock(side_effect=fake_solve)

    snapshot = await runtime.snapshot("session-1")
    assert snapshot.page_state == "ready"
    control = runtime.control_state("session-1")
    assert control["owner"] == "ai"
    assert control["captcha"] is False
