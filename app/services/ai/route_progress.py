"""安全的自动路由阶段事件。"""

from collections.abc import Awaitable, Callable
from typing import Any


RouteProgressCallback = Callable[[dict[str, Any]], Awaitable[None]]


def build_route_stage_log(
    stage_id: str,
    title: str,
    *,
    status: str,
    details: str | None = None,
    execution_time_ms: float | None = None,
) -> dict[str, Any]:
    """Build a user-safe SSE log without exposing router internals."""
    event: dict[str, Any] = {
        "type": "log",
        "id": f"route:{stage_id}",
        "title": title,
        "category": "router",
        "status": status,
    }
    if details:
        event["details"] = details
    if execution_time_ms is not None:
        event["execution_time_ms"] = max(1.0, float(execution_time_ms))
    return event


async def emit_route_stage(
    callback: RouteProgressCallback | None,
    stage_id: str,
    title: str,
    *,
    status: str,
    details: str | None = None,
    execution_time_ms: float | None = None,
) -> None:
    """Forward a route-stage event when the caller is streaming progress."""
    if callback is None:
        return
    await callback(
        build_route_stage_log(
            stage_id,
            title,
            status=status,
            details=details,
            execution_time_ms=execution_time_ms,
        )
    )
