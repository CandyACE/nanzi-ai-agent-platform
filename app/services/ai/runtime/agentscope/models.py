from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AgentScopeModelConfig:
    api_key: str | None
    base_url: str | None
    model: str
    temperature: float = 0.0
    streaming: bool = True
    max_retries: int = 3
    context_size: int | None = None
    max_output_tokens: int | None = None
    provider: str | None = None
    thinking_enable: bool = False
    thinking_capable: bool = False
    reasoning_effort: str | None = None


def _chat_template_kwargs(config: AgentScopeModelConfig) -> dict[str, Any] | None:
    """Build provider-specific thinking controls for OpenAI-compatible APIs.

    Thinking-capable models that default to reasoning still need an explicit
    ``false`` so omitting the field does not leave thinking on.
    """
    if not config.thinking_enable and not config.thinking_capable:
        return None
    kwargs: dict[str, Any] = {
        "thinking": bool(config.thinking_enable),
        "enable_thinking": bool(config.thinking_enable),
    }
    if config.thinking_enable and config.reasoning_effort is not None:
        kwargs["reasoning_effort"] = config.reasoning_effort
    return kwargs


def create_openai_chat_model(config: AgentScopeModelConfig):
    if not config.api_key:
        raise ValueError(f"LLM API Key is missing for model '{config.model}'")

    try:
        from agentscope.credential import OpenAICredential
        from agentscope.model import OpenAIChatModel
    except Exception as exc:
        raise RuntimeError(
            "AgentScope OpenAI chat model dependencies are not available"
        ) from exc

    chat_template_kwargs = _chat_template_kwargs(config)

    class PlatformOpenAIChatModel(OpenAIChatModel):
        """Keep native AgentScope parameters and inject template controls."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self._chat_template_kwargs = dict(chat_template_kwargs or {})
            super().__init__(*args, **kwargs)

        async def _call_api(self, *args: Any, **kwargs: Any) -> Any:
            if self._chat_template_kwargs:
                extra_body = dict(kwargs.get("extra_body") or {})
                extra_body.setdefault(
                    "chat_template_kwargs",
                    dict(self._chat_template_kwargs),
                )
                kwargs["extra_body"] = extra_body
            return await super()._call_api(*args, **kwargs)

    parameters = OpenAIChatModel.Parameters(
        temperature=config.temperature,
        max_tokens=config.max_output_tokens,
        thinking_enable=config.thinking_enable,
        reasoning_effort=config.reasoning_effort,
    )
    model_kwargs = {
        "credential": OpenAICredential(
            api_key=config.api_key,
            base_url=config.base_url,
        ),
        "model": config.model,
        "stream": config.streaming,
        "parameters": parameters,
        "max_retries": config.max_retries,
    }
    if config.provider == "azure":
        from app.utils.model_providers import azure_openai_request_config

        azure_base_url, api_version = azure_openai_request_config(
            config.base_url,
            config.model,
        )
        model_kwargs["credential"] = OpenAICredential(
            api_key=config.api_key,
            base_url=azure_base_url,
        )
        model_kwargs["client_kwargs"] = {
            "default_headers": {"api-key": config.api_key},
            "default_query": {"api-version": api_version},
        }
    if config.context_size is not None:
        model_kwargs["context_size"] = config.context_size

    return PlatformOpenAIChatModel(
        **model_kwargs,
    )
