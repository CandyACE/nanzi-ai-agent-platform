import pytest
from app.api.v1.endpoints.sandbox import (
    DockerWorkspaceEnsureRequest,
    DockerWorkspaceExecRequest,
    ensure_docker_workspace_endpoint,
    stop_docker_workspace_endpoint,
    restart_docker_workspace_endpoint,
    exec_docker_workspace_endpoint,
    get_docker_workspace_status_endpoint,
)
from app.services.ai.runtime.agentscope.workspace import DockerSandboxUnavailableError

pytestmark = pytest.mark.no_infrastructure


@pytest.mark.asyncio
async def test_stop_docker_workspace_endpoint(monkeypatch):
    captured = {}

    async def fake_stop(**kwargs):
        captured.update(kwargs)
        return {
            "status": "stopped",
            "execution_backend": "docker",
            "workspace_id": "alice__1",
            "container_id": None,
        }

    monkeypatch.setattr(
        "app.api.v1.endpoints.sandbox.stop_docker_workspace_runtime",
        fake_stop,
    )

    response = await stop_docker_workspace_endpoint(
        body=DockerWorkspaceEnsureRequest(conversation_id="conv-123"),
        user_info={"id": 1, "username": "alice"},
    )
    assert response.data["status"] == "stopped"
    assert response.data["workspace_id"] == "alice__1"
    assert captured["conversation_id"] == "conv-123"
    assert captured["user_id"] == 1
    assert captured["user_name"] == "alice"


@pytest.mark.asyncio
async def test_restart_docker_workspace_endpoint(monkeypatch):
    captured = {}

    async def fake_restart(**kwargs):
        captured.update(kwargs)
        return {
            "status": "running",
            "execution_backend": "docker",
            "workspace_id": "alice__1",
            "container_id": "new-container-456",
            "started_at": "2026-08-24T05:40:00Z",
            "uptime_seconds": 0,
        }

    monkeypatch.setattr(
        "app.api.v1.endpoints.sandbox.restart_docker_workspace_runtime",
        fake_restart,
    )

    response = await restart_docker_workspace_endpoint(
        body=DockerWorkspaceEnsureRequest(conversation_id="conv-123"),
        user_info={"id": 1, "username": "alice"},
    )
    assert response.data["status"] == "running"
    assert response.data["container_id"] == "new-container-456"
    assert captured["conversation_id"] == "conv-123"


@pytest.mark.asyncio
async def test_exec_docker_workspace_endpoint_success(monkeypatch):
    captured = {}

    async def fake_exec(**kwargs):
        captured.update(kwargs)
        return {
            "stdout": "total 4\n-rw-r--r-- 1 root root 12 Aug 24 05:40 test.txt\n",
            "stderr": "",
            "output": "total 4\n-rw-r--r-- 1 root root 12 Aug 24 05:40 test.txt\n",
            "exit_code": 0,
            "duration_ms": 15,
            "workdir": "/workspace",
            "container_id": "container-123",
        }

    monkeypatch.setattr(
        "app.api.v1.endpoints.sandbox.exec_docker_workspace_command_runtime",
        fake_exec,
    )

    response = await exec_docker_workspace_endpoint(
        body=DockerWorkspaceExecRequest(
            conversation_id="conv-123",
            command="ls -la",
            workdir="/workspace",
        ),
        user_info={"id": 1, "username": "alice"},
    )
    assert response.data["exit_code"] == 0
    assert "test.txt" in response.data["stdout"]
    assert response.data["duration_ms"] == 15
    assert captured["command"] == "ls -la"
    assert captured["workdir"] == "/workspace"


@pytest.mark.asyncio
async def test_exec_docker_workspace_endpoint_not_running(monkeypatch):
    async def fake_exec(**kwargs):
        raise DockerSandboxUnavailableError(
            "Docker sandbox container is not running",
            reason_code="docker_container_not_running",
            user_message="Docker 容器未在运行中，请先启动容器后再进入终端。",
        )

    monkeypatch.setattr(
        "app.api.v1.endpoints.sandbox.exec_docker_workspace_command_runtime",
        fake_exec,
    )

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await exec_docker_workspace_endpoint(
            body=DockerWorkspaceExecRequest(
                conversation_id="conv-123",
                command="pwd",
            ),
            user_info={"id": 1, "username": "alice"},
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["reason_code"] == "docker_container_not_running"


@pytest.mark.asyncio
async def test_exec_docker_workspace_command_function(monkeypatch):
    from app.services.ai.runtime.agentscope.workspace import exec_docker_workspace_command
    from unittest.mock import AsyncMock, MagicMock

    class FakeMessage:
        def __init__(self, data: bytes, stream: int = 1):
            self.data = data
            self.stream = stream

    class FakeStream:
        def __init__(self):
            self.messages = [
                FakeMessage(b"hello world\n", 1),
                FakeMessage(b"", 1),
            ]
            self.idx = 0

        async def read_out(self):
            if self.idx < len(self.messages):
                msg = self.messages[self.idx]
                self.idx += 1
                if not msg.data:
                    return None
                return msg
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return None

    class FakeExec:
        def start(self, detach=False):
            return FakeStream()

        async def inspect(self):
            return {"ExitCode": 0}

    class FakeContainer:
        def __init__(self):
            self.id = "cnt-123"

        async def show(self):
            return {"State": {"Running": True}, "Id": "cnt-123"}

        async def exec(self, **kwargs):
            return FakeExec()

    class FakeDocker:
        def __init__(self):
            self.containers = MagicMock()
            self.containers.get = AsyncMock(return_value=FakeContainer())

        async def close(self):
            pass

    monkeypatch.setattr(
        "app.services.config_service.ConfigService.get",
        AsyncMock(return_value="docker"),
    )
    monkeypatch.setattr(
        "aiodocker.Docker",
        FakeDocker,
    )

    res = await exec_docker_workspace_command(
        user_id=1,
        user_name="alice",
        conversation_id="conv-123",
        command="echo 'hello world'",
    )
    assert res["exit_code"] == 0
    assert "hello world" in res["stdout"]
    assert res["container_id"] == "cnt-123"

