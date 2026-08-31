"""Bounded, JSON-safe copies used for execution-audit persistence and responses."""

from __future__ import annotations

import json
import math
from typing import Any


DEFAULT_AUDIT_PAYLOAD_BYTES = 64 * 1024


def _json_bytes(value: Any) -> bytes:
    # SQLAlchemy's JSON serializer uses ASCII escaping by default. Use the
    # conservative representation here so the database bind value cannot
    # exceed the advertised byte budget for CJK/emoji text.
    return json.dumps(value, ensure_ascii=True, default=str, allow_nan=False).encode("utf-8")


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _truncate_utf8(value: str, max_bytes: int) -> str:
    if max_bytes <= 0:
        return ""
    encoded = value.encode("utf-8")
    if len(encoded) <= max_bytes:
        return value
    return encoded[:max_bytes].decode("utf-8", errors="ignore")


def bound_audit_payload(value: Any, *, max_bytes: int = DEFAULT_AUDIT_PAYLOAD_BYTES) -> Any:
    """Return an independent payload whose serialized JSON is at most ``max_bytes``.

    The runtime keeps using the original value. This function is intentionally
    called only while creating or returning an audit representation.
    """
    if max_bytes < 128:
        raise ValueError("max_bytes must be at least 128")

    copied = _json_safe(value)
    original_bytes = len(_json_bytes(copied))
    if original_bytes <= max_bytes:
        return copied

    metadata = {
        "truncated": True,
        "original_bytes": original_bytes,
        "max_bytes": max_bytes,
    }
    source_preview = _json_bytes(copied).decode("utf-8", errors="replace")
    wrapper_overhead = len(_json_bytes({"__audit_trace": metadata, "preview": ""}))
    preview = _truncate_utf8(source_preview, max_bytes - wrapper_overhead)

    # The first estimate can lose a byte or two at a UTF-8 boundary or because
    # the escaped preview length changes. Reduce until the hard bound holds.
    result = {"__audit_trace": metadata, "preview": preview}
    while len(_json_bytes(result)) > max_bytes and preview:
        preview = _truncate_utf8(preview, max(0, len(preview.encode("utf-8")) - 16))
        result["preview"] = preview
    return result
