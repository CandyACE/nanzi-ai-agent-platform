import pytest


pytestmark = pytest.mark.no_infrastructure


def test_docker_sandbox_error_uses_safe_user_message():
    from app.services.ai.agent_service import _format_execution_error_for_user
    from app.services.ai.runtime.agentscope.workspace import DockerSandboxUnavailableError

    error = DockerSandboxUnavailableError(
        "permission denied while connecting to /var/run/docker.sock",
        reason_code="docker_daemon_unavailable",
        user_message="Docker 沙箱不可用，Bash 未执行。请检查 Docker daemon 权限。",
    )

    assert _format_execution_error_for_user(error) == (
        "Docker 沙箱不可用，Bash 未执行。请检查 Docker daemon 权限。"
    )
