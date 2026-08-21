from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SYSTEM_CONFIG = PROJECT_ROOT / "frontend/src/views/SystemConfig.vue"


def test_system_config_does_not_expose_docker_host_workdir_setting():
    source = SYSTEM_CONFIG.read_text(encoding="utf-8")

    assert "sandbox_docker_host_workdir" not in source
    assert "sandbox_docker_base_image" in source
