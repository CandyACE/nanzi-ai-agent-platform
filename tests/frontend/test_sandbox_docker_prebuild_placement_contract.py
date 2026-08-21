from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure
ROOT = Path(__file__).resolve().parents[2]
SETTINGS = ROOT / "frontend/src/views/SystemConfig.vue"


def test_docker_prebuild_controls_follow_the_base_image_selector():
    source = SETTINGS.read_text(encoding="utf-8")

    image_row = source.index("item.key === 'sandbox_docker_base_image'")
    prebuild_button = source.index('@click="executeDockerPrebuild"')
    prebuild_status = source.index("镜像尚未预构建")

    assert image_row < prebuild_button < prebuild_status


def test_docker_prebuild_status_checks_after_configs_load_and_has_manual_refresh():
    source = SETTINGS.read_text(encoding="utf-8")

    assert "onMounted(async () =>" in source
    assert "await fetchConfigs()" in source
    assert "刷新状态" in source
    assert '@click="refreshDockerPrebuildStatus()"' in source


def test_docker_prebuild_exposes_manual_download_fallback():
    source = SETTINGS.read_text(encoding="utf-8")

    assert "manual_download" in source
    assert "download_url" in source
    assert "manual_import_command" in source
    assert "复制命令" in source
