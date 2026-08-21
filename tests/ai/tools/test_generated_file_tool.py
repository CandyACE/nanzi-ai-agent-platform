from pathlib import Path

import pytest

from app.core.context import AgentContext, set_agent_context


pytestmark = pytest.mark.no_infrastructure


class _FakeArtifactSession:
    def __init__(self):
        self.added = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        return None


@pytest.fixture
def publish_env(tmp_path, monkeypatch):
    from app.services.ai.runtime.agentscope import workspace
    from app.services.ai.tools import generated_file_service

    root = tmp_path / "agent_workspaces"
    user_root = root / "7"
    docs_dir = user_root / "docs"
    docs_dir.mkdir(parents=True)

    async def workspace_root():
        return str(root)

    monkeypatch.setattr(workspace, "resolve_workspace_root", workspace_root)
    monkeypatch.setattr(generated_file_service, "_workspace_root", workspace_root)
    monkeypatch.setattr(
        generated_file_service,
        "AsyncSessionLocal",
        lambda: _FakeArtifactSession(),
    )
    set_agent_context(
        AgentContext(
            agent_id="agent",
            agent_name="Agent",
            user_id=7,
            conversation_id="conv-1",
            trace_id="trace-1",
        )
    )
    return root, docs_dir


@pytest.mark.asyncio
async def test_publish_generated_file_returns_download_url_for_docker_path(publish_env):
    from app.services.ai.tools.generated_file_tool import publish_generated_file

    root, docs_dir = publish_env
    source = docs_dir / "report.md"
    source.write_text("# report", encoding="utf-8")

    result = await publish_generated_file.ainvoke({
        "path": "/workspace/docs/report.md",
    })

    assert result["status"] == "ok"
    assert result["filename"] == "report.md"
    assert result["artifact_type"] == "markdown"
    assert result["download_url"].startswith("/api/v1/chat/generated-files/")
    assert "token=" in result["download_url"]
    assert result["expires_at"]
    assert Path(root / "7" / "docs" / "report.md").read_text(encoding="utf-8") == "# report"


@pytest.mark.asyncio
async def test_publish_generated_file_rejects_another_users_workspace(publish_env):
    from app.services.ai.tools.generated_file_tool import publish_generated_file

    root, _ = publish_env
    secret = root / "8" / "docs" / "secret.md"
    secret.parent.mkdir(parents=True)
    secret.write_text("secret", encoding="utf-8")

    with pytest.raises(ValueError, match="当前用户工作区"):
        await publish_generated_file.ainvoke({"path": str(secret)})


def test_publish_generated_file_is_system_implicit():
    from app.services.ai.tools.registry import ToolRegistry

    names = {
        getattr(tool, "name", "")
        for tool in ToolRegistry.get_system_implicit_tools()
    }

    assert "publish_generated_file" in names
    assert ToolRegistry._registry["publish_generated_file"].name == "publish_generated_file"
