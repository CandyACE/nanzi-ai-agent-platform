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


def test_docker_prebuild_success_reconciles_reused_or_built_state():
    source = SETTINGS.read_text(encoding="utf-8")

    assert "data?.reused || data?.built" in source


def test_docker_prebuild_exposes_faq_help_fallback():
    source = SETTINGS.read_text(encoding="utf-8")

    assert "FAQ.md" in source
    assert "dockerPrebuildHelpUrl" in source
    assert "查看 FAQ" in source
