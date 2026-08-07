from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas.ai_model import AIModelCreate, AIModelResponse, AIModelUpdate


pytestmark = pytest.mark.no_infrastructure

ROOT = Path(__file__).resolve().parents[1]


def model_payload(**overrides):
    payload = {
        "name": "Thinking model",
        "model_id": "thinking-model",
        "provider": "openai",
        "type": "llm",
    }
    payload.update(overrides)
    return payload


def test_thinking_configuration_defaults_to_agent_scope_values():
    model = AIModelCreate(**model_payload())

    assert model.thinking_enable is False
    assert model.thinking_only is False
    assert model.allow_disable_thinking is True
    assert model.reasoning_effort is None
    assert model.supported_reasoning_efforts == [
        "none", "minimal", "low", "medium", "high", "xhigh",
    ]


def test_thinking_configuration_normalizes_effort_order_and_legacy_response_text():
    model = AIModelCreate(
        **model_payload(
            reasoning_effort="xhigh",
            supported_reasoning_efforts=["xhigh", "low"],
        )
    )
    assert model.supported_reasoning_efforts == ["low", "xhigh"]

    now = datetime.now(timezone.utc)
    response = AIModelResponse.from_orm_custom(
        SimpleNamespace(
            id="model-id",
            name="Thinking model",
            model_id="thinking-model",
            provider="openai",
            type="llm",
            api_base_url=None,
            context_size=None,
            max_output_tokens=None,
            thinking_enable=True,
            thinking_only=False,
            allow_disable_thinking=True,
            reasoning_effort="xhigh",
            supported_reasoning_efforts='["xhigh", "low"]',
            is_active=True,
            created_at=now,
            updated_at=now,
            api_key="encrypted-key",
        )
    )
    assert response.supported_reasoning_efforts == ["low", "xhigh"]
    assert response.has_api_key is True


@pytest.mark.parametrize(
    "payload",
    [
        model_payload(reasoning_effort="unsupported"),
        model_payload(supported_reasoning_efforts=[]),
        model_payload(reasoning_effort="high", supported_reasoning_efforts=["low"]),
        model_payload(supported_reasoning_efforts=["unsupported"]),
    ],
)
def test_thinking_configuration_rejects_unsupported_values(payload):
    with pytest.raises(ValidationError):
        AIModelCreate(**payload)


def test_thinking_update_validates_default_against_effective_supported_values():
    with pytest.raises(ValidationError):
        AIModelUpdate(
            reasoning_effort="high",
            supported_reasoning_efforts=["low"],
        )


def test_thinking_migrations_define_agent_scope_efforts():
    mysql = (ROOT / "db-prod/V117-use_agentscope_reasoning_fields.sql").read_text(
        encoding="utf-8"
    )
    postgres = (ROOT / "db-prod-pg/V16-use_agentscope_reasoning_fields.sql").read_text(
        encoding="utf-8"
    )

    for migration in (mysql, postgres):
        for column in ("thinking_enable", "reasoning_effort"):
            assert column in migration
        for effort in ("none", "minimal", "low", "medium", "high", "xhigh"):
            assert effort in migration
