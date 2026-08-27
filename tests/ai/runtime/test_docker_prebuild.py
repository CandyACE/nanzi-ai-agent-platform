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
async def test_prebuild_returns_faq_help_when_daemon_unavailable(
    monkeypatch, tmp_path
):
    from app.services.ai.runtime.agentscope import docker_prebuild

    context_dir = tmp_path / "context"
    context_dir.mkdir()

    events = []

    async def fake_prepare_context(base_image_override=None):
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

    result = await docker_prebuild.prebuild_docker_workspace_image()

    assert result["docker_available"] is False
    assert result["reason_code"] == "docker_daemon_unavailable"
    assert result["tag"] == "agentscope-workspace:abc123def456"
    assert "FAQ.md" in result["help_url"]
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
        lambda _override=None: _async_value(
            ("/tmp/unused-context", "agentscope-workspace:abc123def456")
        ),
    )
    monkeypatch.setitem(__import__("sys").modules, "aiodocker", FakeAioDocker)

    assert await docker_prebuild.docker_workspace_image_prebuilt() is False


@pytest.mark.asyncio
async def test_prebuild_returns_faq_help_when_aiodocker_is_missing(
    monkeypatch,
):
    from app.services.ai.runtime.agentscope import docker_prebuild

    context_dir = "/tmp/unused-context"
    monkeypatch.setattr(
        docker_prebuild,
        "_prepare_context",
        lambda _override=None: _async_value((context_dir, "agentscope-workspace:abc123def456")),
    )
    monkeypatch.setitem(__import__("sys").modules, "aiodocker", None)

    result = await docker_prebuild.prebuild_docker_workspace_image()

    assert result["docker_available"] is False
    assert result["reason_code"] == "aiodocker_unavailable"
    assert "FAQ.md" in result["help_url"]


async def _async_value(value):
    return value


@pytest.mark.asyncio
async def test_prebuild_passes_fileobj_to_aiodocker(monkeypatch, tmp_path):
    from app.services.ai.runtime.agentscope import docker_prebuild

    context_dir = tmp_path / "context"
    context_dir.mkdir()
    (context_dir / "Dockerfile").write_text("FROM python:3.11-slim\n")

    build_calls = []

    class FakeImages:
        async def inspect(self, tag):
            raise Exception("not found")

        async def build(self, **kwargs):
            build_calls.append(kwargs)
            yield {"stream": "Step 1/2 : FROM python:3.11-slim\n"}
            yield {"stream": "Successfully built abcdef123456\n"}

    class FakeDocker:
        def __init__(self):
            self.images = FakeImages()

        async def close(self):
            pass

    class FakeAioDockerModule:
        Docker = FakeDocker

    monkeypatch.setattr(
        docker_prebuild,
        "_prepare_context",
        lambda _override=None: _async_value((str(context_dir), "agentscope-workspace:test123456")),
    )
    monkeypatch.setattr(
        docker_prebuild,
        "check_docker_daemon",
        lambda _aiodocker: _async_value({"available": True, "reason_code": None, "message": "ok"}),
    )
    monkeypatch.setattr(
        docker_prebuild,
        "_mark_prebuilt",
        lambda _base=None: _async_value(None),
    )
    monkeypatch.setitem(__import__("sys").modules, "aiodocker", FakeAioDockerModule)

    result = await docker_prebuild.prebuild_docker_workspace_image()

    assert result["built"] is True
    assert result["reused"] is False
    assert result["tag"] == "agentscope-workspace:test123456"
    assert len(build_calls) == 1
    assert "fileobj" in build_calls[0]
    assert build_calls[0]["tag"] == "agentscope-workspace:test123456"
    assert build_calls[0]["encoding"] == "identity"


@pytest.mark.asyncio
async def test_prebuild_forwards_docker_stream_events(monkeypatch, tmp_path):
    from app.services.ai.runtime.agentscope import docker_prebuild

    context_dir = tmp_path / "context_events"
    context_dir.mkdir()
    received_events = []

    class FakeImages:
        async def inspect(self, tag):
            raise Exception("not found")

        async def build(self, **kwargs):
            yield {"stream": "Step 1/2 : FROM python:3.11-slim\n"}
            yield {"status": "Successfully built abcdef123456\n"}

    class FakeDocker:
        def __init__(self):
            self.images = FakeImages()

        async def close(self):
            pass

    class FakeAioDockerModule:
        Docker = FakeDocker

    async def on_event(event):
        received_events.append(event)

    monkeypatch.setattr(
        docker_prebuild,
        "_prepare_context",
        lambda _override=None: _async_value((str(context_dir), "agentscope-workspace:events123")),
    )
    monkeypatch.setattr(
        docker_prebuild,
        "check_docker_daemon",
        lambda _aiodocker: _async_value({"available": True, "reason_code": None, "message": "ok"}),
    )
    monkeypatch.setattr(
        docker_prebuild,
        "_mark_prebuilt",
        lambda _base=None: _async_value(None),
    )
    monkeypatch.setitem(__import__("sys").modules, "aiodocker", FakeAioDockerModule)

    result = await docker_prebuild.prebuild_docker_workspace_image(on_event=on_event)

    assert result["built"] is True
    assert [event["message"] for event in received_events if event["type"] == "log"] == [
        "Step 1/2 : FROM python:3.11-slim",
        "Successfully built abcdef123456",
    ]


@pytest.mark.asyncio
async def test_prebuild_with_custom_base_image(monkeypatch, tmp_path):
    from app.services.ai.runtime.agentscope import docker_prebuild

    context_dir = tmp_path / "context_custom"
    context_dir.mkdir()

    called_images = []

    async def fake_prepare(override=None):
        called_images.append(override)
        return str(context_dir), f"agentscope-workspace:tag-{override}"

    class FakeImages:
        async def inspect(self, tag):
            return True

    class FakeDocker:
        def __init__(self):
            self.images = FakeImages()

        async def close(self):
            pass

    class FakeAioDockerModule:
        Docker = FakeDocker

    saved_base_images = []

    async def fake_mark(base=None):
        saved_base_images.append(base)

    monkeypatch.setattr(docker_prebuild, "_prepare_context", fake_prepare)
    monkeypatch.setattr(
        docker_prebuild,
        "check_docker_daemon",
        lambda _aiodocker: _async_value({"available": True, "reason_code": None, "message": "ok"}),
    )
    monkeypatch.setattr(docker_prebuild, "_mark_prebuilt", fake_mark)
    monkeypatch.setitem(__import__("sys").modules, "aiodocker", FakeAioDockerModule)

    result = await docker_prebuild.prebuild_docker_workspace_image(base_image="python:3.11")

    assert result["reused"] is True
    assert result["tag"] == "agentscope-workspace:tag-python:3.11"
    assert called_images == ["python:3.11"]
    assert saved_base_images == ["python:3.11"]

