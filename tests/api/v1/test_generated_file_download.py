from httpx import ASGITransport, AsyncClient
import pytest

from app.core.context import AgentContext, set_agent_context


pytestmark = pytest.mark.no_infrastructure


@pytest.mark.asyncio
async def test_generated_file_download_uses_capability_token(tmp_path, monkeypatch):
    from app.main import app
    from app.services.ai.tools import generated_file_service

    class FakeSession:
        def __init__(self):
            self.record = None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        def add(self, value):
            self.record = value

        async def commit(self):
            return None

        async def get(self, model, artifact_id):
            return self.record if self.record and self.record.id == artifact_id else None

    workspace_root = tmp_path / "agent_workspaces"
    workspace_root.mkdir()
    session = FakeSession()
    async def fake_workspace_root():
        return workspace_root
    async def fake_config_get(key, default=None):
        return None
    monkeypatch.setattr(generated_file_service, "_workspace_root", fake_workspace_root)
    monkeypatch.setattr(generated_file_service, "AsyncSessionLocal", lambda: session)
    monkeypatch.setattr(generated_file_service.ConfigService, "get", fake_config_get)
    source = tmp_path / "source.xlsx"
    source.write_bytes(b"workbook")
    set_agent_context(
        AgentContext(agent_id="agent", agent_name="Agent", user_id=7)
    )
    artifact = await generated_file_service.publish(
        source,
        "report.xlsx",
        owner_user_id=7,
        artifact_type="excel",
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(artifact.download_url)

    assert response.status_code == 200
    assert response.content == b"workbook"
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@pytest.mark.asyncio
async def test_generated_file_download_rejects_fake_artifact_url(tmp_path, monkeypatch):
    from app.main import app
    from app.services.ai.tools import generated_file_service

    workspace_root = tmp_path / "agent_workspaces"
    workspace_root.mkdir()

    async def fake_workspace_root():
        return workspace_root

    monkeypatch.setattr(generated_file_service, "_workspace_root", fake_workspace_root)
    monkeypatch.setattr(generated_file_service, "generated_files_root", lambda: tmp_path / "generated")

    fake_url = "/api/v1/chat/generated-files/abcdef0123456789abcdef0123456789?token=fake"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(fake_url)

    assert response.status_code == 404
