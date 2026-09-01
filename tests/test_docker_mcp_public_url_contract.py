from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure

ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILES = (
    ROOT / "docker/docker-compose.yml",
    ROOT / "docker/docker-compose.ai-agent.yml",
)


def test_docker_compose_passes_app_public_url_into_api_container():
    for compose_file in COMPOSE_FILES:
        source = compose_file.read_text(encoding="utf-8")
        assert "APP_PUBLIC_URL=${APP_PUBLIC_URL:-}" in source


def test_docker_guides_explain_echo_public_url_and_host_validation():
    docker_readme = (ROOT / "docker/README.md").read_text(encoding="utf-8")
    echo_readme = (ROOT / "docs/md/mcp_echo_test_server.md").read_text(encoding="utf-8")

    assert "APP_PUBLIC_URL" in docker_readme
    assert "Invalid Host header" in echo_readme
    assert "APP_PUBLIC_URL" in echo_readme
