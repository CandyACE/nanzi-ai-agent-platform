from __future__ import annotations

import logging
from dataclasses import dataclass
from collections.abc import Mapping
from typing import Any, Iterable, List, Optional

from app.services.ai.agent_prompts import AgentServicePrompts
from app.services.ai.prompt_sections import PromptSection, render_prompt_sections
from app.services.ai.turn_decision import TurnDecision

NANZI_PROMPT_CACHE_BOUNDARY = "\n<!-- NANZI_CACHE_BOUNDARY -->\n"
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AssembledSystemPrompt:
    full_text: str
    stable_prefix: str
    dynamic_suffix: str
    cache_boundary_enabled: bool
    cache_reorder_enabled: bool
    section_names: tuple[str, ...] = ()
    section_char_counts: dict[str, int] | None = None


@dataclass
class PromptAssemblyInput:
    agent_system_prompt: Optional[str]
    agent_config: Any
    engine_type: str
    skills_injection: List[str]
    skills_already_loaded: bool
    skills_dir: str
    ltm_profile: Optional[str] = None
    memory_recall_hint: Optional[str] = None
    preloaded_memories: Optional[str] = None
    user_profile: Optional[str] = None
    accessible_resources: Optional[str] = None
    cache_boundary_enabled: bool = False
    cache_reorder_enabled: bool = False
    sub_agents_context: Optional[str] = None
    quick_suggestions_forbidden: bool = False
    runtime_tool_names: Optional[Iterable[str]] = None
    turn_decision: Optional[TurnDecision] = None


def resolve_effective_prompt_tool_names(
    agent_config: Any,
    *,
    current_user_query: str | None = None,
    turn_decision: TurnDecision | None = None,
) -> set[str]:
    """Build the tool inventory shown to the model for the current turn.

    The published tool configuration is the source of truth. Disabled tools
    are excluded so the model cannot call a name that AgentScope did not
    register. When the production current-turn boundary is available, apply
    the same gate used by the runtime so prompt inventory and executable tools
    cannot drift apart.
    """
    names: set[str] = set()
    for item in getattr(agent_config, "tools", None) or []:
        if isinstance(item, Mapping):
            if item.get("enabled", True) is False:
                continue
            name = item.get("name")
        elif isinstance(item, str):
            name = item
        else:
            if getattr(item, "enabled", True) is False:
                continue
            name = getattr(item, "name", "")
        normalized = str(name or "").strip()
        if normalized:
            names.add(normalized)

    try:
        from app.services.ai.tools.registry import ToolRegistry

        names.update(
            str(getattr(tool, "name", "") or "").strip()
            for tool in ToolRegistry.get_system_implicit_tools()
            if str(getattr(tool, "name", "") or "").strip()
        )
    except Exception:
        pass

    try:
        from app.services.ai.skill_resolver import is_main_general_agent

        if is_main_general_agent(agent_config):
            names.add("sub_agent_call")
            names.add("sub_agent_batch_call")
            names.add("todo_write")
    except Exception:
        pass

    return names


async def resolve_effective_prompt_tool_names_for_turn(
    agent_config: Any,
    *,
    current_user_query: str,
    turn_decision: TurnDecision,
) -> set[str]:
    """Resolve prompt names for the turn directly from configured and implicit tools."""
    return resolve_effective_prompt_tool_names(agent_config)


def _prepend_block(current: str, block: Optional[str]) -> str:
    trimmed = (block or "").strip()
    if not trimmed:
        return current
    base = (current or "").strip()
    if base:
        return f"{trimmed}\n\n{base}"
    return trimmed


def _join_blocks(blocks: List[str]) -> str:
    return "\n\n".join(block.strip() for block in blocks if block and block.strip())


def _skills_or_discovery_block(
    *,
    skills_injection: List[str],
    skills_already_loaded: bool,
    skills_dir: str,
) -> str:
    if skills_injection:
        return AgentServicePrompts.skills_profile(skills_injection)
    if not skills_already_loaded:
        return AgentServicePrompts.skill_discovery_hint(skills_dir)
    return ""


async def resolve_prompt_assembler_flags() -> tuple[bool, bool]:
    import asyncio

    from app.services.config_service import ConfigService

    boundary_raw, reorder_raw = await asyncio.gather(
        ConfigService.get("agent_prompt_cache_boundary_enabled", "false"),
        ConfigService.get("agent_prompt_cache_reorder_enabled", "false"),
    )

    def _enabled(raw: Optional[str]) -> bool:
        return str(raw or "").strip().lower() in {"1", "true", "yes", "on"}

    return _enabled(boundary_raw), _enabled(reorder_raw)


def _build_stack_without_platform(params: PromptAssemblyInput) -> str:
    """Mirror AgentService prepend order: skills -> ltm -> recall -> preloaded -> user_profile."""
    prompt = (params.agent_system_prompt or "").strip()
    skills_block = _skills_or_discovery_block(
        skills_injection=params.skills_injection,
        skills_already_loaded=params.skills_already_loaded,
        skills_dir=params.skills_dir,
    )
    prompt = _prepend_block(prompt, skills_block)
    prompt = _prepend_block(prompt, params.ltm_profile)
    prompt = _prepend_block(prompt, params.memory_recall_hint)
    prompt = _prepend_block(prompt, params.preloaded_memories)
    prompt = _prepend_block(prompt, params.accessible_resources)
    prompt = _prepend_block(prompt, params.user_profile)
    prompt = _prepend_block(
        prompt,
        AgentServicePrompts.turn_decision_context(params.turn_decision),
    )
    return prompt


def _platform_global_only(params: PromptAssemblyInput) -> str:
    if (params.engine_type or "LOCAL") != "LOCAL":
        return ""
    return AgentServicePrompts.prepend_platform_global_system_prompt(
        None,
        agent_config=params.agent_config,
        quick_suggestions_forbidden=params.quick_suggestions_forbidden,
        runtime_tool_names=params.runtime_tool_names,
    ).strip()


def assemble_system_prompt(params: PromptAssemblyInput) -> AssembledSystemPrompt:
    stack_without_platform = _build_stack_without_platform(params)
    platform_global = _platform_global_only(params)
    if params.sub_agents_context:
        platform_global = _join_blocks([platform_global, params.sub_agents_context])
    agent_db = (params.agent_system_prompt or "").strip()

    dynamic_sections = [
        PromptSection(
            name=name,
            order=index,
            text=text,
            stability="dynamic",
            source="runtime",
        )
        for index, (name, text) in enumerate(
            (
                ("turn_decision", AgentServicePrompts.turn_decision_context(params.turn_decision)),
                ("accessible_resources", params.accessible_resources),
                ("preloaded_memories", params.preloaded_memories),
                ("memory_recall", params.memory_recall_hint),
                ("ltm_profile", params.ltm_profile),
                (
                    "skills",
                    _skills_or_discovery_block(
                        skills_injection=params.skills_injection,
                        skills_already_loaded=params.skills_already_loaded,
                        skills_dir=params.skills_dir,
                    ),
                ),
            )
        )
        if text and text.strip()
    ]
    dynamic_suffix = render_prompt_sections(dynamic_sections)

    section_blocks = [
        PromptSection("platform_global", 0, platform_global, stability="stable", source="platform"),
        PromptSection(
            "turn_decision",
            10,
            AgentServicePrompts.turn_decision_context(params.turn_decision),
            source="router",
        ),
        PromptSection("user_profile", 20, params.user_profile, source="user_context"),
        PromptSection(
            "accessible_resources",
            25,
            params.accessible_resources,
            source="resource_catalog",
        ),
        PromptSection("preloaded_memories", 30, params.preloaded_memories, source="memory"),
        PromptSection("memory_recall", 40, params.memory_recall_hint, source="memory"),
        PromptSection("ltm_profile", 50, params.ltm_profile, source="memory"),
        PromptSection(
            "skills",
            60,
            _skills_or_discovery_block(
                skills_injection=params.skills_injection,
                skills_already_loaded=params.skills_already_loaded,
                skills_dir=params.skills_dir,
            ),
            source="skill",
        ),
        PromptSection("agent_system_prompt", 70, params.agent_system_prompt, stability="stable", source="agent"),
    ]
    section_names = tuple(
        section.name
        for section in sorted(section_blocks, key=lambda item: (item.order, item.name))
        if section.enabled and section.text and section.text.strip()
    )
    section_char_counts = {
        section.name: len(section.text.strip())
        for section in section_blocks
        if section.enabled and section.text and section.text.strip()
    }

    if params.cache_reorder_enabled:
        stable_prefix = _join_blocks([part for part in [platform_global, params.user_profile, agent_db] if part])
        if params.cache_boundary_enabled and dynamic_suffix:
            full_text = f"{stable_prefix}{NANZI_PROMPT_CACHE_BOUNDARY}{dynamic_suffix}"
        elif params.cache_boundary_enabled:
            full_text = stable_prefix
        else:
            full_text = _join_blocks([stable_prefix, dynamic_suffix]) if dynamic_suffix else stable_prefix
        return AssembledSystemPrompt(
            full_text=full_text,
            stable_prefix=stable_prefix,
            dynamic_suffix=dynamic_suffix,
            cache_boundary_enabled=params.cache_boundary_enabled,
            cache_reorder_enabled=True,
            section_names=section_names,
            section_char_counts=section_char_counts,
        )

    if (params.engine_type or "LOCAL") == "LOCAL":
        if params.cache_boundary_enabled and platform_global and stack_without_platform:
            full_text = f"{platform_global}{NANZI_PROMPT_CACHE_BOUNDARY}{stack_without_platform}"
        else:
            full_text = AgentServicePrompts.prepend_platform_global_system_prompt(
                stack_without_platform or None,
                agent_config=params.agent_config,
                quick_suggestions_forbidden=params.quick_suggestions_forbidden,
                runtime_tool_names=params.runtime_tool_names,
            )
    else:
        full_text = stack_without_platform

    stable_prefix = _join_blocks([part for part in [platform_global, params.user_profile, agent_db] if part])
    return AssembledSystemPrompt(
        full_text=full_text,
        stable_prefix=stable_prefix,
        dynamic_suffix=dynamic_suffix,
        cache_boundary_enabled=params.cache_boundary_enabled,
        cache_reorder_enabled=False,
        section_names=section_names,
        section_char_counts=section_char_counts,
    )
