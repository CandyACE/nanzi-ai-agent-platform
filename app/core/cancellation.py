from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def current_task_cancelling() -> bool:
    task = asyncio.current_task()
    return task is not None and task.cancelling() > 0


def spawn_detached(coro: Coroutine[Any, Any, T], *, name: str) -> asyncio.Task[T]:
    """Run *coro* on a new task so request cancellation cannot interrupt it."""
    task = asyncio.create_task(coro, name=name)

    def _log_failure(done: asyncio.Task[T]) -> None:
        if done.cancelled():
            return
        exc = done.exception()
        if exc is not None:
            logger.warning("detached %s failed: %s", name, exc)

    task.add_done_callback(_log_failure)
    return task


async def await_unless_cancelling(
    factory: Callable[[], Awaitable[T]],
    *,
    name: str,
) -> T | None:
    """Await *factory()* unless this task is being cancelled; then detach it."""
    if current_task_cancelling():
        spawn_detached(factory(), name=name)
        return None
    return await factory()
