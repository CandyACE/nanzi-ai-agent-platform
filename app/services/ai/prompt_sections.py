"""Named prompt sections used for deterministic assembly and inspection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class PromptSection:
    """One prompt block and the metadata needed to inspect its trust/cache role."""

    name: str
    order: int
    text: str
    enabled: bool = True
    stability: str = "dynamic"
    source: str = "runtime"
    trust: str = "trusted"


def render_prompt_sections(sections: Iterable[PromptSection]) -> str:
    """Render enabled, non-empty sections in deterministic order."""
    ordered = sorted(sections, key=lambda section: (section.order, section.name))
    return "\n\n".join(
        section.text.strip()
        for section in ordered
        if section.enabled and section.text and section.text.strip()
    )


__all__ = ["PromptSection", "render_prompt_sections"]
