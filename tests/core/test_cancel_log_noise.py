import asyncio
import io
import logging

import pytest

from app.core.cancellation import await_unless_cancelling, spawn_detached
from app.core.logging_filters import (
    CancelledPoolTerminateFilter,
    install_cancellation_log_filters,
)


pytestmark = pytest.mark.no_infrastructure


@pytest.mark.asyncio
async def test_await_unless_cancelling_runs_inline_when_not_cancelled():
    ran = asyncio.Event()

    async def work():
        ran.set()

    await await_unless_cancelling(work, name="inline")
    assert ran.is_set()


@pytest.mark.asyncio
async def test_await_unless_cancelling_detaches_after_task_cancel():
    ran = asyncio.Event()

    async def work():
        await asyncio.sleep(0)
        ran.set()

    async def body():
        try:
            await asyncio.sleep(30)
        finally:
            await await_unless_cancelling(work, name="detached-audit")

    task = asyncio.create_task(body())
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.wait_for(ran.wait(), timeout=1)


@pytest.mark.asyncio
async def test_spawn_detached_logs_failures(caplog):
    async def boom():
        raise RuntimeError("detached-boom")

    with caplog.at_level(logging.WARNING, logger="app.core.cancellation"):
        task = spawn_detached(boom(), name="boom-task")
        with pytest.raises(RuntimeError, match="detached-boom"):
            await asyncio.wait_for(task, timeout=1)

    assert any("detached-boom" in rec.getMessage() for rec in caplog.records)


def test_pool_terminate_filter_drops_cancelled_error():
    filt = CancelledPoolTerminateFilter()
    record = logging.LogRecord(
        name="sqlalchemy.pool",
        level=logging.ERROR,
        pathname="pool.py",
        lineno=1,
        msg="Exception terminating connection %r",
        args=("<conn>",),
        exc_info=(asyncio.CancelledError, asyncio.CancelledError(), None),
    )
    assert filt.filter(record) is False


def test_pool_terminate_filter_keeps_other_errors():
    filt = CancelledPoolTerminateFilter()
    record = logging.LogRecord(
        name="sqlalchemy.pool",
        level=logging.ERROR,
        pathname="pool.py",
        lineno=1,
        msg="Exception terminating connection %r",
        args=("<conn>",),
        exc_info=(RuntimeError, RuntimeError("disk"), None),
    )
    assert filt.filter(record) is True


def test_pool_terminate_filter_keeps_unrelated_errors():
    filt = CancelledPoolTerminateFilter()
    record = logging.LogRecord(
        name="sqlalchemy.pool",
        level=logging.ERROR,
        pathname="pool.py",
        lineno=1,
        msg="Exception during reset or similar",
        args=(),
        exc_info=(asyncio.CancelledError, asyncio.CancelledError(), None),
    )
    assert filt.filter(record) is True


def test_install_filters_child_pool_logger_through_stream_handler():
    install_cancellation_log_filters()
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.ERROR)
    child = logging.getLogger("sqlalchemy.pool.impl.AsyncAdaptedQueuePool")
    child.handlers[:] = [handler]
    child.propagate = False
    child.setLevel(logging.ERROR)
    try:
        child.error(
            "Exception terminating connection %r",
            "<conn>",
            exc_info=(asyncio.CancelledError, asyncio.CancelledError("Cancelled via cancel scope"), None),
        )
        assert "Exception terminating connection" not in stream.getvalue()
    finally:
        child.handlers.remove(handler)
