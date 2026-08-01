import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.services.ai import agent_service as agent_service_module
from app.services.ai.agent_service import AgentService
from app.services.ai.agent_service import build_current_model_answer
from app.services.ai.config import RuntimeModelInfo


pytestmark = pytest.mark.no_infrastructure


def test_build_current_model_answer_reports_configured_and_effective_identity():
    answer = build_current_model_answer(
        RuntimeModelInfo(
            configured_model="团队默认模型",
            effective_model_id="deepseek-chat",
            source="agent_config",
            phase="primary_agent",
            resolution_status="registry_resolved",
        )
    )

    assert "deepseek-chat" in answer
    assert "团队默认模型" in answer
    assert "主模型" in answer


def test_build_current_model_answer_is_honest_when_registry_resolution_failed():
    answer = build_current_model_answer(
        RuntimeModelInfo(
            configured_model="团队默认模型",
            effective_model_id="团队默认模型",
            source="agent_config",
            phase="primary_agent",
            resolution_status="registry_unresolved",
        )
    )

    assert "团队默认模型" in answer
    assert "无法确认" in answer


@pytest.mark.asyncio
async def test_chat_completion_answers_model_identity_without_dispatching_executor(monkeypatch):
    service = AgentService()
    config = SimpleNamespace(
        agent_id="agent-1",
        agent_name="general",
        agent_display_name="通用助手",
        model_name="团队默认模型",
    )
    resolved = RuntimeModelInfo(
        configured_model="团队默认模型",
        effective_model_id="deepseek-chat",
        source="agent_config",
        phase="primary_agent",
        resolution_status="registry_resolved",
    )

    monkeypatch.setattr(
        service,
        "_resolve_and_verify_agent",
        AsyncMock(return_value=(config, None, 0.0, None)),
    )
    monkeypatch.setattr(
        agent_service_module,
        "resolve_runtime_model_info",
        AsyncMock(return_value=resolved),
    )
    dispatch = AsyncMock(side_effect=AssertionError("model identity must not dispatch an executor"))
    monkeypatch.setattr(service, "_dispatch_executor", dispatch)
    monkeypatch.setattr(agent_service_module.AuditManager, "log_transaction", AsyncMock())

    result = await service.chat_completion(
        [{"role": "user", "content": "你当前的模型是什么"}],
        agent_id="agent-1",
    )

    assert result["status"] == "success"
    assert "deepseek-chat" in result["content"]
    dispatch.assert_not_awaited()
