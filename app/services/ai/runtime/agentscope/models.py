from __future__ import annotations

from dataclasses import dataclass


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

    parameters = OpenAIChatModel.Parameters(
        temperature=config.temperature,
        max_tokens=config.max_output_tokens,
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
    if config.context_size is not None:
        model_kwargs["context_size"] = config.context_size

    return OpenAIChatModel(
        **model_kwargs,
    )
