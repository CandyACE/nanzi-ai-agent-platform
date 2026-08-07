"""Resolve registered-model reasoning defaults and request-scoped overrides."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Mapping

from app.schemas.ai_model import DEFAULT_SUPPORTED_REASONING_EFFORTS

logger = logging.getLogger(__name__)

UNSET = object()


@dataclass(frozen=True)
class ReasoningSettings:
    thinking_enable: bool
    reasoning_effort: str | None


def _supported_efforts(value: Any) -> list[str]:
    if value is None:
        return list(DEFAULT_SUPPORTED_REASONING_EFFORTS)
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return []
    if not isinstance(value, (list, tuple, set)):
        return []
    return [str(item) for item in value]


def resolve_reasoning_settings(
    *,
    thinking_enable: bool,
    reasoning_effort: str | None,
    thinking_only: bool = False,
    allow_disable_thinking: bool = True,
    supported_reasoning_efforts: Any = None,
    overrides: Mapping[str, Any] | None = None,
) -> ReasoningSettings:
    """Apply request-level overrides to a registered model's default reasoning state.

    ``thinking_only`` is the registered default state, while ``thinking_enable``
    is the model capability. Explicit session values may override the default;
    disabling is additionally gated by ``allow_disable_thinking``.
    """
    supported = _supported_efforts(supported_reasoning_efforts)
    effective_thinking = bool(thinking_enable and thinking_only)
    effective_effort = reasoning_effort
    options = overrides or {}

    requested_thinking = options.get("thinking_enable", UNSET)
    if isinstance(requested_thinking, bool):
        if requested_thinking:
            if thinking_enable:
                effective_thinking = True
            else:
                logger.warning("Ignoring thinking_enable=true for a non-thinking model")
        elif effective_thinking and allow_disable_thinking:
            effective_thinking = False
        elif effective_thinking:
            logger.warning("Ignoring unauthorized thinking disable request")

    requested_effort = options.get("reasoning_effort", UNSET)
    if requested_effort is not UNSET and requested_effort is not None:
        if effective_thinking and requested_effort in supported:
            effective_effort = str(requested_effort)
        else:
            logger.warning("Ignoring unsupported reasoning effort: %s", requested_effort)

    if not effective_thinking:
        effective_effort = None
    elif effective_effort is not None and effective_effort not in supported:
        logger.warning("Ignoring invalid registered reasoning effort: %s", effective_effort)
        effective_effort = None

    return ReasoningSettings(
        thinking_enable=effective_thinking,
        reasoning_effort=effective_effort,
    )
