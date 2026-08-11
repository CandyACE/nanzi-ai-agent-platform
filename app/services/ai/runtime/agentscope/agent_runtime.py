from __future__ import annotations

import logging
from typing import Any

from app.schemas.agent import ChatConfig
from app.services.ai.runtime.agentscope.tools import RuntimeToolSpec

logger = logging.getLogger(__name__)


def _config_flag_enabled(raw: Any, *, default: bool = True) -> bool:
    if raw is None or str(raw).strip() == "":
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


async def load_injection_config(*, inject_runtime_state: bool | None = None) -> Any:
    """Build AgentScope InjectionConfig with platform timezone.

    AgentScope 默认已开启 runtime state 注入（时区 UTC）。此处显式绑定
    ``platform_timezone``；可用系统配置 ``agentscope_inject_runtime_state``
    关闭。可选 ``agentscope_inject_time_interval_hours`` 控制时间重复注入间隔。
    不改变工具链 / HITL，仅影响上下文 hint。
    """
    from agentscope.agent import InjectionConfig
    from app.services.config_service import ConfigService
    from app.services.platform_timezone import get_cached_platform_timezone

    enabled = inject_runtime_state
    if enabled is None:
        raw = await ConfigService.get("agentscope_inject_runtime_state")
        enabled = _config_flag_enabled(raw, default=True)

    interval_raw = await ConfigService.get("agentscope_inject_time_interval_hours")
    try:
        time_interval = float(interval_raw) if interval_raw not in (None, "") else 0.5
    except (TypeError, ValueError):
        time_interval = 0.5
    time_interval = min(max(time_interval, 0.0), 24.0)

    return InjectionConfig(
        inject_runtime_state=bool(enabled),
        timezone=get_cached_platform_timezone(),
        time_interval=time_interval,
    )


def build_runtime_middlewares(
    *,
    user_id: str | int | None,
    conversation_id: str | None,
    agent_name: str | None = None,
    trace_id: str | None = None,
) -> list[Any]:
    """Assemble Agent middlewares: forbidden-tool DENY + audit + model-call stats."""
    from app.services.ai.runtime.agentscope.middleware import (
        ModelCallStatsMiddleware,
        ToolPermissionMiddleware,
    )

    async def _forbidden_tools_deny_override(
        *,
        agent: Any,
        input_kwargs: dict[str, Any],
        decision: Any,
    ) -> Any:
        del agent, decision
        from app.services.ai.runtime.agentscope.tools import enforce_tool_forbidden

        tool = input_kwargs.get("tool")
        tool_call = input_kwargs.get("tool_call")
        tool_name = getattr(tool, "name", None) or getattr(tool_call, "name", None)
        if not tool_name:
            return None
        return await enforce_tool_forbidden(str(tool_name), user_id)

    middlewares: list[Any] = [
        ToolPermissionMiddleware(
            user_id=user_id,
            conversation_id=conversation_id,
            agent_name=agent_name,
            deny_override=_forbidden_tools_deny_override,
        )
    ]
    if conversation_id:
        middlewares.append(
            ModelCallStatsMiddleware(
                user_id=user_id,
                conversation_id=conversation_id,
                agent_name=agent_name,
                trace_id=trace_id,
            )
        )
    return middlewares


async def load_context_config() -> Any:
    """Build AgentScope ContextConfig from platform settings."""
    from agentscope.agent import ContextConfig
    from app.services.config_service import ConfigService

    async def _float(key: str, default: float) -> float:
        raw = await ConfigService.get(key)
        try:
            return float(raw) if raw not in (None, "") else default
        except (TypeError, ValueError):
            return default

    async def _int(key: str, default: int) -> int:
        raw = await ConfigService.get(key)
        try:
            return int(raw) if raw not in (None, "") else default
        except (TypeError, ValueError):
            return default

    trigger_ratio = await _float("agentscope_context_trigger_ratio", 0.8)
    reserve_ratio = await _float("agentscope_context_reserve_ratio", 0.1)
    tool_result_limit = await _int("agentscope_tool_result_limit", 2000)

    trigger_ratio = min(max(trigger_ratio, 0.5), 0.89)
    reserve_ratio = min(max(reserve_ratio, 0.05), trigger_ratio - 0.05)

    return ContextConfig(
        trigger_ratio=trigger_ratio,
        reserve_ratio=reserve_ratio,
        tool_result_limit=tool_result_limit,
    )


async def build_model_config(
    *,
    config: ChatConfig | None,
    primary_model_name: str,
) -> Any:
    """Build AgentScope ModelConfig with optional fallback model."""
    from agentscope.agent import ModelConfig
    from app.services.ai.config import AgentConfigProvider

    fallback_model = None
    try:
        fallback_handle = await AgentConfigProvider.get_fallback_llm(
            streaming=True,
            config=config,
            exclude_model=primary_model_name,
        )
        fallback_model = (
            getattr(fallback_handle, "native_model", None) if fallback_handle else None
        )
    except Exception as exc:
        logger.warning("[agent_runtime] Failed to load fallback model: %s", exc)
    return ModelConfig(fallback_model=fallback_model, max_retries=0)


def build_tools_fingerprint(
    config: ChatConfig,
    tools: list[RuntimeToolSpec],
) -> str:
    import hashlib
    import json

    tool_names = sorted(spec.name for spec in tools)
    payload = {
        "agent_name": config.agent_name,
        "agent_version": config.agent_version,
        "model_name": config.model_name,
        "tools": tool_names,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
