import importlib
import json
from pathlib import Path

import pytest

from app.core.context import AgentContext, set_agent_context, set_debug_context
from app.services.ai.tools.registry import ToolRegistry


pytestmark = pytest.mark.no_infrastructure


def _session_status_tool():
    tool = ToolRegistry._registry.get("session_status")
    assert tool is not None, "session_status must be registered before it can be invoked"
    return tool


def _install_context(*, conversation_id: str | None = "conv-1") -> None:
    set_agent_context(
        AgentContext(
            agent_id="agent-1",
            agent_name="助手",
            engine_type="LOCAL",
            user_id=123,
            conversation_id=conversation_id,
            is_admin=False,
            user_dimensions={
                "id": 123,
                "user_name": "alice",
                "real_name": "Alice",
                "role": "analyst",
                "dept_code": "D01",
                "org_path": "总部/数据部",
                "extra_data": {"api_key": "must-not-leak"},
            },
            dataset_ids=["dataset-1"],
            knowledge_dataset_ids=["kb-1"],
            metadata_dataset_ids=["meta-1"],
            skills=["skill-1"],
            runtime_model_info={
                "configured_model": "primary-alias",
                "effective_model_id": "provider-model",
                "source": "agent_config",
                "phase": "primary_agent",
                "is_fallback": False,
                "resolution_status": "registry_resolved",
                "context_size": 131072,
                "max_output_tokens": 8192,
                "provider": "openai-compatible",
                "thinking_enable": True,
                "thinking_capable": True,
                "reasoning_effort": "medium",
                "api_key": "must-not-leak",
                "base_url": "https://secret.example.invalid/v1",
            },
            authorized_attachment_paths=["/private/attachment/sales.xlsx"],
            current_turn_attachment_paths=["/private/attachment/sales.xlsx"],
            permission_options={"mode": "allow"},
        )
    )
    set_debug_context(
        {
            "injected_context": {
                "device_type": "移动端(小屏幕)",
                "display_hint": "窄屏排版优化",
            }
        }
    )


def test_session_status_returns_safe_current_context_snapshot(tmp_path: Path, monkeypatch):
    _install_context()
    module = importlib.import_module("app.services.ai.tools.session_status")

    user_root = tmp_path / "alice__123"
    session_workdir = user_root / "sessions" / "conv-1"
    docs_dir = user_root / "docs"
    session_workdir.mkdir(parents=True)
    docs_dir.mkdir(parents=True)

    async def fake_workspace_root(**_kwargs):
        return str(tmp_path)

    monkeypatch.setattr(module, "resolve_workspace_root", fake_workspace_root)

    class FakeRedis:
        async def lrange(self, key, start, end):
            return [
                json.dumps(
                    {
                        "input_tokens": 1200,
                        "output_tokens": 80,
                        "timestamp": "2026-08-15T10:00:00+00:00",
                    }
                )
            ]

    async def fake_get_redis():
        return FakeRedis()

    monkeypatch.setattr(module, "get_redis", fake_get_redis)

    payload = json.loads(_session_status_tool().invoke({}))

    assert payload["scope"] == "current_session"
    assert payload["session"]["conversation_id"] == "conv-1"
    assert payload["session"]["agent_name"] == "助手"
    assert payload["client"] == {
        "device_type": "移动端(小屏幕)",
        "display_hint": "窄屏排版优化",
        "source": "client_reported",
    }
    assert payload["workspace"]["session_workdir"] == {
        "path": str(session_workdir),
        "exists": True,
        "writable": True,
    }
    assert payload["workspace"]["docs_dir"] == {
        "path": str(docs_dir),
        "exists": True,
        "writable": True,
        "scope": "cross_session",
    }
    assert payload["model"]["context_window_tokens"] == 131072
    assert payload["context_usage"]["last_input_tokens"] == 1200
    assert payload["context_usage"]["last_output_tokens"] == 80
    assert payload["user"]["user_name"] == "alice"
    assert payload["attachments"] == {
        "authorized_count": 1,
        "current_turn_count": 1,
        "filenames": ["sales.xlsx"],
    }


def test_session_status_excludes_secrets_and_internal_objects(tmp_path: Path, monkeypatch):
    _install_context()
    module = importlib.import_module("app.services.ai.tools.session_status")

    async def fake_workspace_root(**_kwargs):
        return str(tmp_path)

    async def fake_get_redis():
        return None

    monkeypatch.setattr(module, "resolve_workspace_root", fake_workspace_root)
    monkeypatch.setattr(module, "get_redis", fake_get_redis)

    payload = json.loads(_session_status_tool().invoke({}))
    serialized = json.dumps(payload, ensure_ascii=False)

    assert "api_key" not in serialized
    assert "base_url" not in serialized
    assert "engine_config" not in serialized
    assert "permission_options" not in serialized
    assert "/private/attachment" not in serialized
    assert "must-not-leak" not in serialized


def test_session_status_is_parameterless_and_handles_missing_context(monkeypatch):
    set_agent_context(None)
    set_debug_context({})

    tool = _session_status_tool()
    assert tool.args_schema.model_fields == {}

    module = importlib.import_module("app.services.ai.tools.session_status")

    async def fake_get_redis():
        return None

    monkeypatch.setattr(module, "get_redis", fake_get_redis)
    payload = json.loads(tool.invoke({}))

    assert payload["scope"] == "current_session"
    assert payload["session"]["conversation_id"] is None
    assert payload["user"] is None
    assert payload["limitations"]


@pytest.mark.asyncio
async def test_workspace_root_read_only_resolution_does_not_create_directory(tmp_path, monkeypatch):
    from app.services.ai.runtime.agentscope import workspace

    missing_root = tmp_path / "not-created"
    monkeypatch.setattr(workspace, "default_workspace_root", lambda: str(missing_root))

    resolved = await workspace.resolve_workspace_root(ensure_exists=False)

    assert resolved == str(missing_root)
    assert not missing_root.exists()


@pytest.mark.asyncio
async def test_session_status_is_read_only_runtime_state_tool():
    from app.services.ai.grounding.models import EvidenceType

    spec = await ToolRegistry.get_runtime_tool("session_status")

    assert spec.permission_scope == "read"
    assert spec.is_read_only is True
    assert spec.evidence_types == frozenset({EvidenceType.RUNTIME_STATE})
    assert "不要猜测" in spec.description
