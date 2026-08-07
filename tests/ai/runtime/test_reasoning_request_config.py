from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


pytestmark = pytest.mark.no_infrastructure


@pytest.mark.parametrize(
    ("thinking_enable", "reasoning_effort"),
    [(False, None), (True, None), (True, "low"), (True, "xhigh")],
)
def test_agentscope_model_config_carries_native_reasoning_parameters(
    thinking_enable,
    reasoning_effort,
):
    from app.services.ai.runtime.agentscope.models import AgentScopeModelConfig

    config = AgentScopeModelConfig(
        api_key="sk-test",
        base_url="https://llm.example.com/v1",
        model="thinking-model",
        thinking_enable=thinking_enable,
        reasoning_effort=reasoning_effort,
    )

    assert config.thinking_enable is thinking_enable
    assert config.reasoning_effort == reasoning_effort


@pytest.mark.asyncio
async def test_runtime_model_info_carries_registered_reasoning_configuration(monkeypatch):
    from app.services.ai import config as config_module

    monkeypatch.setattr(
        config_module.ConfigService,
        "get_all_from_db",
        AsyncMock(return_value={}),
    )
    monkeypatch.setattr(
        config_module,
        "_lookup_registered_model",
        AsyncMock(return_value=SimpleNamespace(
            model_id="registered-model",
            api_key=None,
            api_base_url=None,
            context_size=None,
            max_output_tokens=None,
            provider="openai",
            thinking_enable=True,
            reasoning_effort="xhigh",
        )),
    )

    info = await config_module.resolve_runtime_model_info(model_override="registered-model")

    assert info.thinking_enable is True
    assert info.reasoning_effort == "xhigh"


def test_llm_factory_carries_native_reasoning_parameters_into_model_config(monkeypatch):
    from app.core.llm.client import LLMFactory
    from app.services.ai.runtime.agentscope.models import AgentScopeModelConfig

    captured = {}

    def fake_create_model(config: AgentScopeModelConfig):
        captured["config"] = config
        return SimpleNamespace(model=config.model)

    monkeypatch.setattr(
        "app.core.llm.client.create_openai_chat_model",
        fake_create_model,
    )

    LLMFactory.get_chat_model(
        api_key="sk-test",
        base_url="https://llm.example.com/v1",
        model="thinking-model",
        thinking_enable=True,
        reasoning_effort="xhigh",
    )

    assert captured["config"].thinking_enable is True
    assert captured["config"].reasoning_effort == "xhigh"


@pytest.mark.asyncio
async def test_get_llm_async_reads_reasoning_configuration_from_registered_model(monkeypatch):
    from app.core.llm import client

    async def fake_config_get(key):
        return {
            "llm_model_name": "thinking-model",
            "llm_api_key": "system-key",
            "llm_base_url": "https://system.example/v1",
        }.get(key)

    captured = {}

    async def fake_lookup(model):
        return SimpleNamespace(
            model_id=model,
            api_key=None,
            api_base_url=None,
            provider="openai",
            thinking_enable=True,
            reasoning_effort="xhigh",
        )

    def fake_get_chat_model(**kwargs):
        captured.update(kwargs)
        return "handle"

    monkeypatch.setattr(client.ConfigServiceProxy, "get", staticmethod(fake_config_get))
    monkeypatch.setattr(client, "_lookup_ai_model_record", fake_lookup)
    monkeypatch.setattr(client.LLMFactory, "get_chat_model", staticmethod(fake_get_chat_model))

    assert await client.get_llm_async(streaming=False) == "handle"
    assert captured["thinking_enable"] is True
    assert captured["reasoning_effort"] == "xhigh"


@pytest.mark.asyncio
async def test_configured_llm_passes_reasoning_configuration_to_shared_factory(monkeypatch):
    from app.services.ai import config as config_module

    monkeypatch.setattr(
        config_module.ConfigService,
        "get_all_from_db",
        AsyncMock(return_value={}),
    )
    monkeypatch.setattr(
        config_module,
        "_lookup_registered_model",
        AsyncMock(
            return_value=SimpleNamespace(
                model_id="registered-model",
                api_key=None,
                api_base_url=None,
                context_size=None,
                max_output_tokens=None,
                provider="openai",
                thinking_enable=True,
                reasoning_effort="low",
            )
        ),
    )
    captured = {}

    def fake_get_llm(**kwargs):
        captured.update(kwargs)
        return "handle"

    monkeypatch.setattr(config_module, "get_llm", fake_get_llm)

    assert await config_module.AgentConfigProvider.get_configured_llm(
        streaming=True,
        model_override="registered-model",
    ) == "handle"
    assert captured["thinking_enable"] is True
    assert captured["reasoning_effort"] == "low"
