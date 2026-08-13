import asyncio
import contextlib
import os
import time

import pytest

from app.services.ai.runtime.conversation_run_registry import (
    conversation_run_registry,
    track_conversation_run,
)


pytestmark = pytest.mark.no_infrastructure


@pytest.fixture(autouse=True)
def _clear_registry():
    conversation_run_registry.clear()
    yield
    conversation_run_registry.clear()


@pytest.mark.asyncio
async def test_cancel_stops_sleeping_task_before_timeout():
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def _long_run():
        async with track_conversation_run("u1", "conv-1"):
            started.set()
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                cancelled.set()
                raise

    task = asyncio.create_task(_long_run())
    await asyncio.wait_for(started.wait(), timeout=1)
    t0 = time.monotonic()

    stopped = await conversation_run_registry.request_stop(
        user_id="u1",
        conversation_id="conv-1",
    )
    assert stopped is True

    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=2)

    assert cancelled.is_set()
    assert time.monotonic() - t0 < 5


@pytest.mark.asyncio
async def test_cancel_does_not_stop_a_different_conversation():
    started = asyncio.Event()

    async def _long_run():
        async with track_conversation_run("u1", "conv-keep"):
            started.set()
            await asyncio.sleep(0.2)

    task = asyncio.create_task(_long_run())
    await asyncio.wait_for(started.wait(), timeout=1)

    stopped = await conversation_run_registry.request_stop(
        user_id="u1",
        conversation_id="conv-other",
    )
    assert stopped is False
    await asyncio.wait_for(task, timeout=2)
    assert task.exception() is None


@pytest.mark.asyncio
async def test_unregister_does_not_drop_a_newer_run():
    async with track_conversation_run("u1", "conv-1") as first:
        second = conversation_run_registry.register("u1", "conv-1")
        conversation_run_registry.unregister(first)
        assert conversation_run_registry.get("u1", "conv-1") is second
        conversation_run_registry.unregister(second)


@pytest.mark.asyncio
async def test_request_stop_kills_tracked_subprocess():
    if os.name != "posix":
        pytest.skip("process-group stop is POSIX-only")

    started = asyncio.Event()
    pid_box: dict[str, int] = {}

    async def _long_run():
        async with track_conversation_run("u1", "conv-proc") as handle:
            process = await asyncio.create_subprocess_exec(
                "sleep",
                "30",
                start_new_session=True,
            )
            assert handle is not None
            handle.track_process(process)
            pid_box["pid"] = process.pid
            started.set()
            await process.wait()

    task = asyncio.create_task(_long_run())
    await asyncio.wait_for(started.wait(), timeout=1)
    pid = pid_box["pid"]

    stopped = await conversation_run_registry.request_stop(
        user_id="u1",
        conversation_id="conv-proc",
    )
    assert stopped is True
    await asyncio.wait_for(task, timeout=2)

    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


@pytest.mark.asyncio
async def test_cancellable_backend_stops_sleep_on_run_cancel():
    if os.name != "posix":
        pytest.skip("process-group stop is POSIX-only")

    from app.services.ai.runtime.conversation_run_subprocess import CancellableLocalBackend

    started = asyncio.Event()
    backend = CancellableLocalBackend()

    async def _long_run():
        async with track_conversation_run("u1", "conv-bash"):
            started.set()
            await backend.exec_shell(["/bin/sleep", "30"], timeout=30)

    task = asyncio.create_task(_long_run())
    await asyncio.wait_for(started.wait(), timeout=1)
    await asyncio.sleep(0.1)
    t0 = time.monotonic()
    stopped = await conversation_run_registry.request_stop(
        user_id="u1",
        conversation_id="conv-bash",
    )
    assert stopped is True
    with contextlib.suppress(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=2)
    assert time.monotonic() - t0 < 5
