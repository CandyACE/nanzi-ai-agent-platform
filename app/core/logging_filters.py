from __future__ import annotations

import asyncio
import logging

_HANDLER_PATCHED = False
_MESSAGE = "Exception terminating connection"


class CancelledPoolTerminateFilter(logging.Filter):
    """Drop SQLAlchemy pool errors caused by cancelling an in-flight request.

    Stop/abort cancels the SSE task while connections are returned to the pool.
    SQLAlchemy already shields terminate, but AnyIO cancel scopes still interrupt
    it and log a full ERROR traceback. That is noise, not a failed query.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        return not _is_cancelled_pool_terminate(record)


def _is_cancelled_pool_terminate(record: logging.LogRecord) -> bool:
    try:
        message = record.getMessage()
    except Exception:
        message = str(record.msg)
    if _MESSAGE not in message:
        return False
    exc_info = record.exc_info
    if exc_info:
        exc_type, exc, _tb = exc_info
        if isinstance(exc, asyncio.CancelledError):
            return True
        if isinstance(exc_type, type) and issubclass(exc_type, asyncio.CancelledError):
            return True
    blob = " ".join(
        part
        for part in (message, getattr(record, "exc_text", None) or "")
        if part
    )
    return "CancelledError" in blob or "Cancelled via cancel scope" in blob


def install_cancellation_log_filters() -> None:
    """Patch Handler.handle so child pool loggers and uvicorn handlers are covered."""
    global _HANDLER_PATCHED
    filt = CancelledPoolTerminateFilter()
    root = logging.getLogger()
    if not any(isinstance(item, CancelledPoolTerminateFilter) for item in root.filters):
        root.addFilter(filt)
    for handler in list(root.handlers):
        if not any(isinstance(item, CancelledPoolTerminateFilter) for item in handler.filters):
            handler.addFilter(filt)

    if _HANDLER_PATCHED:
        return
    original_handle = logging.Handler.handle

    def handle(self: logging.Handler, record: logging.LogRecord):  # type: ignore[override]
        if _is_cancelled_pool_terminate(record):
            return
        return original_handle(self, record)

    logging.Handler.handle = handle  # type: ignore[method-assign]
    _HANDLER_PATCHED = True
