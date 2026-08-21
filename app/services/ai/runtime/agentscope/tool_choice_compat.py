"""Compatibility helpers for model-specific tool-choice limitations."""

from __future__ import annotations

from typing import Any


def model_thinking_enabled(model: Any) -> bool:
    """Return the effective native-model Thinking state when it is exposed."""
    parameters = getattr(model, "parameters", None)
    if parameters is not None:
        thinking_enable = getattr(parameters, "thinking_enable", None)
        if thinking_enable is not None:
            return bool(thinking_enable)
    return bool(getattr(model, "thinking_enable", False))


def tool_choice_for_model(model: Any, tool_choice: Any) -> Any:
    """Thinking models receive tools through auto selection, not forced choice."""
    if tool_choice is None or model_thinking_enabled(model):
        return None
    return tool_choice
