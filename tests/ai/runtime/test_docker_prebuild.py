import pytest


pytestmark = pytest.mark.no_infrastructure


@pytest.mark.asyncio
async def test_check_docker_daemon_reports_missing_endpoint(monkeypatch):
    from app.services.ai.runtime.agentscope import docker_prebuild

    class FakeAioDocker:
        class Docker:
            def __init__(self):
                raise AssertionError("docker_host is not configured")

    status = await docker_prebuild.check_docker_daemon(FakeAioDocker)

    assert status["available"] is False
    assert status["reason_code"] == "docker_daemon_unavailable"
    assert "DOCKER_HOST" in status["message"]


@pytest.mark.asyncio
async def test_prebuild_returns_manual_download_info_when_daemon_unavailable(
    monkeypatch, tmp_path
):
    from app.services.ai.runtime.agentscope import docker_prebuild

    context_dir = tmp_path / "context"
    context_dir.mkdir()

    events = []

    async def fake_prepare_context():
        events.append("context")
        return str(context_dir), "agentscope-workspace:abc123def456"

    async def fake_check_docker_daemon(_aiodocker):
        events.append("check")
        return {
            "available": False,
            "reason_code": "docker_daemon_unavailable",
            "message": "后端容器无法连接 Docker daemon",
        }

    monkeypatch.setattr(
        docker_prebuild,
        "_prepare_context",
        fake_prepare_context,
    )
    monkeypatch.setattr(
        docker_prebuild,
        "check_docker_daemon",
        fake_check_docker_daemon,
    )
    monkeypatch.setattr(
        docker_prebuild,
        "get_manual_image_download_url",
        lambda: _async_value("https://downloads.example.com/agentscope-workspace.tar"),
    )

    result = await docker_prebuild.prebuild_docker_workspace_image()

    assert result["action"] == "manual_download"
    assert result["docker_available"] is False
    assert result["tag"] == "agentscope-workspace:abc123def456"
    assert (
        result["download_url"]
        == "https://downloads.example.com/agentscope-workspace.tar"
    )
    assert "docker load" in result["manual_import_command"]
    assert events == ["check", "context"]


@pytest.mark.asyncio
async def test_image_prebuilt_check_returns_false_when_daemon_is_unavailable(
    monkeypatch,
):
    from app.services.ai.runtime.agentscope import docker_prebuild

    class FakeAioDocker:
        class Docker:
            def __init__(self):
                raise AssertionError("docker_host is not configured")

    monkeypatch.setattr(
        docker_prebuild,
        "_prepare_context",
        lambda: _async_value(
            ("/tmp/unused-context", "agentscope-workspace:abc123def456")
        ),
    )
    monkeypatch.setattr(
        docker_prebuild,
        "get_manual_image_download_url",
        lambda: _async_value(None),
    )
    monkeypatch.setitem(__import__("sys").modules, "aiodocker", FakeAioDocker)

    assert await docker_prebuild.docker_workspace_image_prebuilt() is False


@pytest.mark.asyncio
async def test_prebuild_returns_manual_download_info_when_aiodocker_is_missing(
    monkeypatch,
):
    from app.services.ai.runtime.agentscope import docker_prebuild

    context_dir = "/tmp/unused-context"
    monkeypatch.setattr(
        docker_prebuild,
        "_prepare_context",
        lambda: _async_value((context_dir, "agentscope-workspace:abc123def456")),
    )
    monkeypatch.setattr(
        docker_prebuild,
        "get_manual_image_download_url",
        lambda: _async_value("https://downloads.example.com/agentscope-workspace.tar"),
    )
    monkeypatch.setitem(__import__("sys").modules, "aiodocker", None)

    result = await docker_prebuild.prebuild_docker_workspace_image()

    assert result["action"] == "manual_download"
    assert result["reason_code"] == "aiodocker_unavailable"
    assert result["download_url"].startswith("https://")


async def _async_value(value):
    return value
