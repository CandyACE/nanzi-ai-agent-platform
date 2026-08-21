import pytest


pytestmark = pytest.mark.no_infrastructure


@pytest.mark.asyncio
async def test_sandbox_connection_endpoint_closes_initialized_workspace(monkeypatch):
    from app.api.v1.endpoints.sandbox import (
        SandboxConnectionTestRequest,
        test_sandbox_connection,
    )

    class FakeWorkspace:
        def __init__(self):
            self.closed = False

        async def close(self):
            self.closed = True

    workspace = FakeWorkspace()
    captured = {}

    async def fake_build(policy, config_overrides):
        captured["policy"] = policy
        captured["config_overrides"] = config_overrides
        return workspace

    monkeypatch.setattr(
        "app.api.v1.endpoints.sandbox.build_sandbox_workspace_for_test",
        fake_build,
    )

    response = await test_sandbox_connection(
        policy="e2b",
        body=SandboxConnectionTestRequest(
            sandbox_e2b_api_key="e2b-test-key",
            sandbox_e2b_template="base",
            sandbox_e2b_timeout_seconds="30",
        ),
        user_info={"role": "admin"},
    )

    assert response.data == {"policy": "e2b", "connected": True}
    assert captured["policy"] == "e2b"
    assert captured["config_overrides"]["sandbox_e2b_api_key"] == "e2b-test-key"
    assert workspace.closed is True
