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


@pytest.mark.asyncio
async def test_docker_prebuild_status_returns_manual_download_state(monkeypatch):
    from app.api.v1.endpoints.sandbox import get_docker_prebuild_status

    monkeypatch.setattr(
        "app.api.v1.endpoints.sandbox.docker_workspace_prebuild_status",
        lambda: _async_value(
            {
                "prebuilt": False,
                "docker_available": False,
                "action": "manual_download",
                "download_url": "https://downloads.example.com/agentscope-workspace.tar",
                "required_image_tag": "agentscope-workspace:abc123def456",
            },
        ),
    )

    response = await get_docker_prebuild_status(user_info={"role": "admin"})

    assert response.data["action"] == "manual_download"
    assert response.data["docker_available"] is False
    assert response.data["download_url"].startswith("https://")


@pytest.mark.asyncio
async def test_ensure_docker_workspace_returns_running_metadata(monkeypatch):
    from app.api.v1.endpoints.sandbox import (
        DockerWorkspaceEnsureRequest,
        ensure_docker_workspace_endpoint,
    )

    fake_workspace = type(
        "FakeWorkspace",
        (),
        {
            "_platform_sandbox_policy": "docker",
            "_platform_execution_backend": "docker",
            "_platform_workspace_id": "alice__1",
            "_platform_container_id": "container-1",
            "is_alive": True,
        },
    )()
    captured = {}

    async def fake_ensure(**kwargs):
        captured.update(kwargs)
        return fake_workspace

    monkeypatch.setattr(
        "app.api.v1.endpoints.sandbox.ensure_docker_workspace_runtime",
        fake_ensure,
    )

    response = await ensure_docker_workspace_endpoint(
        body=DockerWorkspaceEnsureRequest(conversation_id="c1"),
        user_info={"user_id": 1, "user_name": "alice", "role": "user"},
    )

    assert response.data == {
        "status": "running",
        "execution_backend": "docker",
        "workspace_id": "alice__1",
        "container_id": "container-1",
        "started_at": None,
        "uptime_seconds": None,
    }
    assert captured["user_id"] == 1
    assert captured["user_name"] == "alice"
    assert captured["conversation_id"] == "c1"


@pytest.mark.asyncio
async def test_ensure_docker_workspace_rejects_non_docker_policy(monkeypatch):
    from fastapi import HTTPException

    from app.api.v1.endpoints.sandbox import (
        DockerWorkspaceEnsureRequest,
        ensure_docker_workspace_endpoint,
    )
    from app.services.ai.runtime.agentscope.workspace import DockerSandboxUnavailableError

    async def fake_ensure(**kwargs):
        raise DockerSandboxUnavailableError(
            "sandbox policy is local",
            reason_code="docker_policy_not_effective",
            user_message="当前不是 Docker 沙箱模式，无需启动用户 Docker 容器。",
        )

    monkeypatch.setattr(
        "app.api.v1.endpoints.sandbox.ensure_docker_workspace_runtime",
        fake_ensure,
    )

    with pytest.raises(HTTPException) as exc_info:
        await ensure_docker_workspace_endpoint(
            body=DockerWorkspaceEnsureRequest(conversation_id="c1"),
            user_info={"user_id": 1, "user_name": "alice", "role": "user"},
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == {
        "reason_code": "docker_policy_not_effective",
        "message": "当前不是 Docker 沙箱模式，无需启动用户 Docker 容器。",
    }


@pytest.mark.asyncio
async def test_docker_workspace_status_returns_existing_container_metadata(monkeypatch):
    from app.api.v1.endpoints.sandbox import get_docker_workspace_status_endpoint

    captured = {}

    async def fake_status(**kwargs):
        captured.update(kwargs)
        return {
            "status": "running",
            "execution_backend": "docker",
            "workspace_id": "alice__1",
            "container_id": "container-1",
        }

    monkeypatch.setattr(
        "app.api.v1.endpoints.sandbox.docker_workspace_status_runtime",
        fake_status,
    )

    response = await get_docker_workspace_status_endpoint(
        conversation_id="c1",
        user_info={"user_id": 1, "user_name": "alice", "role": "user"},
    )

    assert response.data == {
        "status": "running",
        "execution_backend": "docker",
        "workspace_id": "alice__1",
        "container_id": "container-1",
    }
    assert captured["conversation_id"] == "c1"
    assert captured["user_id"] == 1
    assert captured["user_name"] == "alice"


async def _async_value(value):
    return value
