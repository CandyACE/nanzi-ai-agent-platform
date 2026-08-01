"""Provider presets for OpenAI-compatible model endpoints."""

from __future__ import annotations

from typing import Mapping


# These are SDK ``base_url`` values, not the full ``/chat/completions`` URL.
# Azure and arbitrary compatible gateways are intentionally left configurable.
MODEL_PROVIDER_DEFAULT_BASE_URLS: Mapping[str, str] = {
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com",
    "kimi": "https://api.moonshot.cn/v1",
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
    "siliconflow": "https://api.siliconflow.cn/v1",
    "dashscope": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "ollama": "http://localhost:11434/v1",
}


def default_model_api_base_url(provider: str | None) -> str | None:
    """Return the official/default compatible endpoint for a provider."""

    return MODEL_PROVIDER_DEFAULT_BASE_URLS.get(str(provider or "").strip().lower())


def resolve_model_api_base_url(
    provider: str | None,
    configured_url: str | None,
) -> str | None:
    """Use a configured URL when present, otherwise use the provider preset."""

    normalized_url = (configured_url or "").strip()
    return normalized_url or default_model_api_base_url(provider)
