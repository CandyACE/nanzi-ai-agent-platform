from datetime import datetime
from types import SimpleNamespace
from typing import AsyncIterator

import pytest


pytestmark = pytest.mark.no_infrastructure


class _FakeOpenAIStream:
    def __init__(self, chunks):
        self._chunks = chunks

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    def __aiter__(self):
        return self._iterate()

    async def _iterate(self):
        for chunk in self._chunks:
            yield chunk


def test_llm_factory_builds_agentscope_model_config(monkeypatch):
    from app.core.llm.client import LLMFactory
    from app.services.ai.runtime.agentscope.models import AgentScopeModelConfig

    captured = {}

    def fake_create_model(config: AgentScopeModelConfig):
        captured["config"] = config
        return SimpleNamespace(model=config.model, stream=config.streaming)

    monkeypatch.setattr(
        "app.core.llm.client.create_openai_chat_model",
        fake_create_model,
    )

    model = LLMFactory.get_chat_model(
        streaming=True,
        api_key="sk-test",
        base_url="https://llm.example.com/v1",
        model="deepseek-chat",
        temperature=0.2,
    )

    assert captured["config"] == AgentScopeModelConfig(
        api_key="sk-test",
        base_url="https://llm.example.com/v1",
        model="deepseek-chat",
        temperature=0.2,
        streaming=True,
    )
    assert model.model_name == "deepseek-chat"
    assert model.temperature == 0.2
    assert model.native_model.model == "deepseek-chat"


def test_create_openai_chat_model_uses_agentscope_parameters():
    from app.services.ai.runtime.agentscope.models import (
        AgentScopeModelConfig,
        create_openai_chat_model,
    )

    model = create_openai_chat_model(
        AgentScopeModelConfig(
            api_key="sk-test",
            base_url="https://llm.example.com/v1",
            model="deepseek-chat",
            temperature=0.25,
            streaming=False,
        )
    )

    assert model.model == "deepseek-chat"
    assert model.stream is False
    assert model.parameters.temperature == 0.25


@pytest.mark.asyncio
async def test_openai_chat_model_preserves_each_streamed_text_delta():
    from app.services.ai.runtime.agentscope.models import (
        AgentScopeModelConfig,
        create_openai_chat_model,
    )

    model = create_openai_chat_model(
        AgentScopeModelConfig(
            api_key="sk-test",
            base_url="https://llm.example.com/v1",
            model="deepseek-chat",
            streaming=True,
        )
    )

    def chunk(text):
        return SimpleNamespace(
            id="response-1",
            usage=None,
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(
                        content=text,
                        reasoning_content=None,
                        reasoning=None,
                        audio=None,
                        tool_calls=None,
                    )
                )
            ],
        )

    responses = [
        response
        async for response in model._parse_stream_response(
            datetime.now(),
            _FakeOpenAIStream([chunk("先查"), chunk("一下")]),
        )
    ]

    assert [block.text for response in responses for block in response.content] == [
        "先查",
        "一下",
    ]


def test_create_openai_chat_model_applies_optional_context_and_output_limits():
    from app.services.ai.runtime.agentscope.models import (
        AgentScopeModelConfig,
        create_openai_chat_model,
    )

    model = create_openai_chat_model(
        AgentScopeModelConfig(
            api_key="sk-test",
            base_url="https://llm.example.com/v1",
            model="gpt-test",
            context_size=262144,
            max_output_tokens=65536,
        )
    )

    assert model.context_size == 262144
    assert model.parameters.max_tokens == 65536


def test_create_openai_chat_model_uses_agentscope_reasoning_parameters():
    from app.services.ai.runtime.agentscope.models import (
        AgentScopeModelConfig,
        create_openai_chat_model,
    )

    model = create_openai_chat_model(
        AgentScopeModelConfig(
            api_key="sk-test",
            base_url="https://llm.example.com/v1",
            model="thinking-model",
            thinking_enable=True,
            reasoning_effort="xhigh",
        )
    )

    assert model.parameters.thinking_enable is True
    assert model.parameters.reasoning_effort == "xhigh"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("thinking_enable", "thinking_capable", "reasoning_effort", "expected_template"),
    [
        (True, False, "high", {"thinking": True, "enable_thinking": True, "reasoning_effort": "high"}),
        (True, True, None, {"thinking": True, "enable_thinking": True}),
        (False, False, None, None),
        (False, True, None, {"thinking": False, "enable_thinking": False}),
        (False, True, "high", {"thinking": False, "enable_thinking": False}),
    ],
)
async def test_openai_chat_model_injects_chat_template_kwargs(
    monkeypatch,
    thinking_enable,
    thinking_capable,
    reasoning_effort,
    expected_template,
):
    import openai

    from app.services.ai.runtime.agentscope.models import (
        AgentScopeModelConfig,
        create_openai_chat_model,
    )

    captured = {}

    class FakeCompletions:
        async def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(choices=[], usage=None)

    class FakeClient:
        def __init__(self):
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(openai, "AsyncClient", lambda **kwargs: FakeClient())
    model = create_openai_chat_model(
        AgentScopeModelConfig(
            api_key="sk-test",
            base_url="https://llm.example.com/v1",
            model="thinking-model",
            streaming=False,
            thinking_enable=thinking_enable,
            thinking_capable=thinking_capable,
            reasoning_effort=reasoning_effort,
        )
    )

    await model._call_api("thinking-model", messages=[])

    assert captured.get("extra_body") == (
        {"chat_template_kwargs": expected_template}
        if expected_template is not None
        else None
    )
    assert "chat_template_kwargs" not in captured


def _build_bad_request_error(message: str):
    import httpx
    import openai

    request = httpx.Request("POST", "https://llm.example.com/v1/chat/completions")
    response = httpx.Response(400, request=request)
    return openai.BadRequestError(
        f"Error code: 400 - {message}",
        response=response,
        body={"error": {"code": "invalid_parameter_error", "message": message}},
    )


@pytest.mark.asyncio
async def test_thinking_tool_choice_fallback_disables_thinking_per_request(monkeypatch):
    import openai
    from agentscope.tool import ToolChoice

    from app.services.ai.runtime.agentscope.models import (
        AgentScopeModelConfig,
        create_openai_chat_model,
    )

    requests = []

    class FakeCompletions:
        async def create(self, **kwargs):
            requests.append(kwargs)
            if len(requests) == 1:
                raise _build_bad_request_error(
                    "The tool_choice parameter does not support being set to "
                    "required or object in thinking mode",
                )
            return SimpleNamespace(choices=[], usage=None)

    class FakeClient:
        def __init__(self):
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(openai, "AsyncClient", lambda **kwargs: FakeClient())
    model = create_openai_chat_model(
        AgentScopeModelConfig(
            api_key="sk-test",
            base_url="https://llm.example.com/v1",
            model="thinking-model",
            streaming=False,
            thinking_enable=True,
            reasoning_effort="high",
        ),
    )

    await model._call_api(
        "thinking-model",
        messages=[],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "execute_sql_query",
                    "parameters": {"type": "object"},
                },
            },
        ],
        tool_choice=ToolChoice(mode="execute_sql_query"),
    )

    assert len(requests) == 2
    assert requests[0]["tool_choice"] == {
        "type": "function",
        "function": {"name": "execute_sql_query"},
    }
    assert requests[0]["extra_body"] == {
        "chat_template_kwargs": {
            "thinking": True,
            "enable_thinking": True,
            "reasoning_effort": "high",
        },
    }
    assert requests[0]["reasoning_effort"] == "high"
    assert requests[1]["tool_choice"] == requests[0]["tool_choice"]
    assert requests[1]["extra_body"] == {
        "chat_template_kwargs": {"thinking": False, "enable_thinking": False},
    }
    assert "reasoning_effort" not in requests[1]
    assert model.parameters.thinking_enable is True
    assert model.parameters.reasoning_effort == "high"


@pytest.mark.asyncio
async def test_non_matching_bad_request_does_not_trigger_thinking_tool_choice_fallback(
    monkeypatch,
):
    import openai
    from agentscope.tool import ToolChoice

    from app.services.ai.runtime.agentscope.models import (
        AgentScopeModelConfig,
        create_openai_chat_model,
    )

    requests = []

    class FakeCompletions:
        async def create(self, **kwargs):
            requests.append(kwargs)
            raise _build_bad_request_error("invalid model parameter")

    class FakeClient:
        def __init__(self):
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(openai, "AsyncClient", lambda **kwargs: FakeClient())
    model = create_openai_chat_model(
        AgentScopeModelConfig(
            api_key="sk-test",
            base_url="https://llm.example.com/v1",
            model="thinking-model",
            streaming=False,
            thinking_enable=True,
        ),
    )

    with pytest.raises(openai.BadRequestError, match="invalid model parameter"):
        await model._call_api(
            "thinking-model",
            messages=[],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "execute_sql_query",
                        "parameters": {"type": "object"},
                    },
                },
            ],
            tool_choice=ToolChoice(mode="execute_sql_query"),
        )

    assert len(requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("thinking_enable", "tool_choice_mode"),
    [(True, None), (True, "auto"), (False, "execute_sql_query")],
)
async def test_matching_bad_request_without_fallback_conditions_is_not_retried(
    monkeypatch,
    thinking_enable,
    tool_choice_mode,
):
    import openai
    from agentscope.tool import ToolChoice

    from app.services.ai.runtime.agentscope.models import (
        AgentScopeModelConfig,
        create_openai_chat_model,
    )

    requests = []

    class FakeCompletions:
        async def create(self, **kwargs):
            requests.append(kwargs)
            raise _build_bad_request_error(
                "The tool_choice parameter does not support being set to "
                "required or object in thinking mode",
            )

    class FakeClient:
        def __init__(self):
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(openai, "AsyncClient", lambda **kwargs: FakeClient())
    model = create_openai_chat_model(
        AgentScopeModelConfig(
            api_key="sk-test",
            base_url="https://llm.example.com/v1",
            model="thinking-model",
            streaming=False,
            thinking_enable=thinking_enable,
        ),
    )

    with pytest.raises(openai.BadRequestError, match="tool_choice"):
        await model._call_api(
            "thinking-model",
            messages=[],
            tools=(
                [
                    {
                        "type": "function",
                        "function": {
                            "name": "execute_sql_query",
                            "parameters": {"type": "object"},
                        },
                    },
                ]
                if tool_choice_mode
                else None
            ),
            tool_choice=(
                ToolChoice(mode=tool_choice_mode) if tool_choice_mode else None
            ),
        )

    assert len(requests) == 1


@pytest.mark.asyncio
async def test_model_connection_test_passes_form_token_limits(monkeypatch):
    from app.api.portal.endpoints.models import _test_model_connection
    from app.services.ai.runtime.agentscope import chat as chat_module
    from app.core.llm import client as llm_client

    captured = {}

    async def fake_get_llm_async(**kwargs):
        captured.update(kwargs)
        return object()

    class FakeChatClient:
        async def generate_text(self, messages):
            return "pong"

    monkeypatch.setattr(llm_client, "get_llm_async", fake_get_llm_async)
    monkeypatch.setattr(chat_module, "chat_client_from_handle", lambda handle: FakeChatClient())

    result = await _test_model_connection(
        model_id="qwen3.6-35b",
        model_type="multimodal",
        api_key="sk-test",
        api_base_url="https://llm.example.com/v1",
        context_size=262144,
        max_output_tokens=8192,
    )

    assert result["status"] == "success"
    assert captured["context_size"] == 262144
    assert captured["max_output_tokens"] == 8192


@pytest.mark.asyncio
async def test_get_llm_async_uses_config_service_fallbacks(monkeypatch):
    from app.core.llm import client

    async def fake_config_get(key):
        values = {
            "llm_model_name": "configured-model",
            "llm_api_key": "configured-key",
            "llm_base_url": "https://configured.example/v1",
            "llm_temperature": "0.3",
        }
        return values.get(key)

    captured = {}

    def fake_get_chat_model(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(model_name=kwargs["model"])

    monkeypatch.setattr(client.ConfigServiceProxy, "get", staticmethod(fake_config_get))
    monkeypatch.setattr(client.LLMFactory, "get_chat_model", staticmethod(fake_get_chat_model))
    monkeypatch.setattr(client, "_lookup_ai_model_record", lambda model: None)

    model = await client.get_llm_async(streaming=False)

    assert model.model_name == "configured-model"
    assert captured == {
        "streaming": False,
        "api_key": "configured-key",
        "base_url": "https://configured.example/v1",
        "model": "configured-model",
        "temperature": 0.3,
    }


@pytest.mark.asyncio
async def test_get_llm_async_prefers_model_registry_credentials(monkeypatch):
    from app.core.llm import client

    async def fake_config_get(key):
        values = {
            "llm_model_name": "friendly-name",
            "llm_api_key": "system-key",
            "llm_base_url": "https://system.example/v1",
            "llm_temperature": "0.4",
        }
        return values.get(key)

    captured = {}

    def fake_get_chat_model(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(model_name=kwargs["model"])

    monkeypatch.setattr(client.ConfigServiceProxy, "get", staticmethod(fake_config_get))
    monkeypatch.setattr(client.LLMFactory, "get_chat_model", staticmethod(fake_get_chat_model))
    monkeypatch.setattr(
        client,
        "_lookup_ai_model_record",
        lambda model: SimpleNamespace(
            api_key="model-key",
            api_base_url="https://model.example/v1",
            model_id="real-model-id",
        ),
    )

    await client.get_llm_async(streaming=True)

    assert captured["api_key"] == "model-key"
    assert captured["base_url"] == "https://model.example/v1"
    assert captured["model"] == "real-model-id"
    assert captured["temperature"] == 0.4


@pytest.mark.asyncio
async def test_get_llm_async_uses_model_registry_token_limits(monkeypatch):
    from app.core.llm import client

    async def fake_config_get(key):
        return {
            "llm_model_name": "friendly-name",
            "llm_api_key": "system-key",
            "llm_base_url": "https://system.example/v1",
            "llm_temperature": "0.4",
        }.get(key)

    captured = {}

    def fake_get_chat_model(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(model_name=kwargs["model"])

    monkeypatch.setattr(client.ConfigServiceProxy, "get", staticmethod(fake_config_get))
    monkeypatch.setattr(client.LLMFactory, "get_chat_model", staticmethod(fake_get_chat_model))
    monkeypatch.setattr(
        client,
        "_lookup_ai_model_record",
        lambda model: SimpleNamespace(
            api_key="model-key",
            api_base_url="https://model.example/v1",
            model_id="real-model-id",
            context_size=262144,
            max_output_tokens=65536,
        ),
    )

    await client.get_llm_async(streaming=True)

    assert captured["context_size"] == 262144
    assert captured["max_output_tokens"] == 65536


@pytest.mark.asyncio
async def test_get_llm_async_decrypts_model_registry_credentials(monkeypatch):
    from app.core.llm import client
    from app.utils.encryption import get_api_key_manager

    async def fake_config_get(key):
        return {
            "llm_model_name": "friendly-name",
            "llm_api_key": "system-key",
            "llm_base_url": "https://system.example/v1",
            "llm_temperature": "0.4",
        }.get(key)

    captured = {}

    def fake_get_chat_model(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(model_name=kwargs["model"])

    monkeypatch.setattr(client.ConfigServiceProxy, "get", staticmethod(fake_config_get))
    monkeypatch.setattr(client.LLMFactory, "get_chat_model", staticmethod(fake_get_chat_model))
    monkeypatch.setattr(
        client,
        "_lookup_ai_model_record",
        lambda model: SimpleNamespace(
            api_key=get_api_key_manager().encrypt_api_key("encrypted-model-key"),
            api_base_url="https://model.example/v1",
            model_id="real-model-id",
        ),
    )

    await client.get_llm_async(streaming=True)

    assert captured["api_key"] == "encrypted-model-key"
    assert captured["base_url"] == "https://model.example/v1"
    assert captured["model"] == "real-model-id"


def test_model_credentials_reject_corrupted_versioned_ciphertext():
    from app.utils.model_credentials import ModelCredentialError, decrypt_model_api_key

    with pytest.raises(ModelCredentialError):
        decrypt_model_api_key("modelkey:v1:not-a-valid-ciphertext")


@pytest.mark.asyncio
async def test_llm_handle_provides_executor_compatible_methods():
    from agentscope.message import TextBlock
    from agentscope.model import ChatResponse

    from app.core.llm.client import AgentScopeLLMHandle

    class ArgsSchema:
        @staticmethod
        def model_json_schema():
            return {"type": "object", "properties": {"query": {"type": "string"}}}

    class Tool:
        name = "search"
        description = "Search docs"
        args_schema = ArgsSchema

    class FakeNativeModel:
        async def __call__(self, messages, **kwargs):
            self.messages = messages
            self.kwargs = kwargs
            return ChatResponse(content=[TextBlock(text="ok")], is_last=True)

    native_model = FakeNativeModel()
    handle = AgentScopeLLMHandle(
        native_model=native_model,
        model_name="test-model",
        temperature=0.0,
        streaming=False,
    ).bind_tools([Tool()])

    response = await handle.ainvoke("hello")

    assert response.content == "ok"
    assert native_model.kwargs["tools"][0]["function"]["name"] == "search"


@pytest.mark.asyncio
async def test_llm_handle_streams_executor_compatible_chunks():
    from agentscope.message import TextBlock
    from agentscope.model import ChatResponse

    from app.core.llm.client import AgentScopeLLMHandle

    async def stream() -> AsyncIterator[ChatResponse]:
        yield ChatResponse(content=[TextBlock(text="a")], is_last=False)
        yield ChatResponse(content=[TextBlock(text="b")], is_last=True)

    class FakeNativeModel:
        async def __call__(self, messages, **kwargs):
            return stream()

    handle = AgentScopeLLMHandle(
        native_model=FakeNativeModel(),
        model_name="test-model",
        temperature=0.0,
        streaming=True,
    )

    chunks = []
    async for chunk in handle.astream("hello"):
        chunks.append(chunk.content)

    assert chunks == ["a", "b"]
