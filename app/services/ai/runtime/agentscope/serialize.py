"""JSON-safe serialization for AgentScope runtime payloads.

AgentScope / tool hooks may leak un-awaited coroutines into agent.state.
Pydantic ``model_dump(mode="json")`` then raises:
``Unable to serialize unknown type: <class 'coroutine'>``.
Resolve awaitables first, then dump JSON-compatible structures.
"""

from __future__ import annotations

import inspect
from typing import Any

from pydantic import TypeAdapter


async def resolve_awaitables(
    value: Any,
    *,
    path: str = "value",
    awaitable_cache: dict[int, Any] | None = None,
) -> Any:
    """Recursively await leaked awaitables in nested dict/list/tuple payloads."""
    awaitable_cache = awaitable_cache if awaitable_cache is not None else {}
    if inspect.isawaitable(value):
        cache_key = id(value)
        if cache_key in awaitable_cache:
            return awaitable_cache[cache_key]
        try:
            resolved = await value
            resolved = await resolve_awaitables(
                resolved,
                path=path,
                awaitable_cache=awaitable_cache,
            )
        except Exception as exc:
            raise RuntimeError(
                f"Failed to resolve awaitable while serializing {path}: {exc}",
            ) from exc
        awaitable_cache[cache_key] = resolved
        return resolved
    if isinstance(value, dict):
        return {
            key: await resolve_awaitables(
                item,
                path=f"{path}.{key}",
                awaitable_cache=awaitable_cache,
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            await resolve_awaitables(
                item,
                path=f"{path}[{index}]",
                awaitable_cache=awaitable_cache,
            )
            for index, item in enumerate(value)
        ]
    if isinstance(value, tuple):
        return tuple(
            [
                await resolve_awaitables(
                    item,
                    path=f"{path}[{index}]",
                    awaitable_cache=awaitable_cache,
                )
                for index, item in enumerate(value)
            ],
        )
    if isinstance(value, set):
        return [
            await resolve_awaitables(
                item,
                path=f"{path}[]",
                awaitable_cache=awaitable_cache,
            )
            for item in value
        ]
    return value


def _to_python_tree(value: Any) -> Any:
    if hasattr(value, "model_dump") and callable(value.model_dump):
        try:
            return value.model_dump(mode="python")
        except TypeError:
            return value.model_dump()
    return value


async def serialize_jsonable(
    value: Any,
    *,
    path: str = "value",
    awaitable_cache: dict[int, Any] | None = None,
) -> Any:
    """Convert a runtime object/tree into a JSON-compatible Python structure."""
    python_value = _to_python_tree(value)
    resolved = await resolve_awaitables(
        python_value,
        path=path,
        awaitable_cache=awaitable_cache,
    )
    return TypeAdapter(Any).dump_python(resolved, mode="json")


async def serialize_agent_state(
    state: Any,
    *,
    awaitable_cache: dict[int, Any] | None = None,
) -> dict[str, Any]:
    """Serialize AgentScope agent.state for Redis / pending snapshots."""
    serialized = await serialize_jsonable(
        state,
        path="agent_state",
        awaitable_cache=awaitable_cache,
    )
    if isinstance(serialized, dict):
        return serialized
    return {"value": serialized}
