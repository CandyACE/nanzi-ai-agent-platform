import pytest


pytestmark = pytest.mark.no_infrastructure


def test_docker_policy_is_effective_local_when_platform_runs_in_container(monkeypatch):
    from app.services import config_service

    monkeypatch.setattr(config_service, "get_env", lambda: "docker")

    assert config_service.resolve_effective_sandbox_policy("docker") == "local"
    assert config_service.resolve_effective_sandbox_policy("e2b") == "e2b"


def test_docker_policy_remains_available_on_host(monkeypatch):
    from app.services import config_service

    monkeypatch.setattr(config_service, "get_env", lambda: "host")

    assert config_service.resolve_effective_sandbox_policy("docker") == "docker"


def test_config_update_rejects_docker_policy_inside_container(monkeypatch):
    from app.services import config_service

    monkeypatch.setattr(config_service, "get_env", lambda: "docker")

    with pytest.raises(ValueError, match="平台后端运行在 Docker 容器内"):
        config_service.validate_config_update("sandbox_policy", "docker")


def test_config_update_allows_other_policies_inside_container(monkeypatch):
    from app.services import config_service

    monkeypatch.setattr(config_service, "get_env", lambda: "docker")

    config_service.validate_config_update("sandbox_policy", "local")
    config_service.validate_config_update("sandbox_policy", "e2b")
