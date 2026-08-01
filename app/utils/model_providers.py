"""Provider presets for OpenAI-compatible model endpoints."""

from __future__ import annotations

from typing import Mapping
from urllib.parse import parse_qs, quote, urlsplit, urlunsplit


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


def azure_openai_request_config(
    configured_url: str | None,
    deployment_id: str,
) -> tuple[str, str]:
    """Build the Azure deployment URL and API version for the OpenAI SDK.

    The UI stores the resource endpoint and optionally accepts
    ``?api-version=...``. Azure uses the model registry's ``model_id`` as the
    deployment name, rather than sending it as a normal OpenAI model name.
    """

    raw_url = (configured_url or "").strip().rstrip("/")
    if not raw_url:
        raise ValueError("Azure OpenAI 需要填写资源 Endpoint")
    parsed = urlsplit(raw_url)
    query = parse_qs(parsed.query)
    api_version = (query.get("api-version") or ["2024-10-21"])[0]
    base_path = parsed.path.rstrip("/")
    # This is the SDK base URL. AgentScope/OpenAI appends
    # ``chat/completions`` when it performs a chat request.
    deployment_path = f"{base_path}/openai/deployments/{quote(deployment_id, safe='')}"
    base_url = urlunsplit((parsed.scheme, parsed.netloc, deployment_path, "", ""))
    return base_url, api_version
