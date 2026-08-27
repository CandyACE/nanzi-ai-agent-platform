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


def test_docker_base_image_is_excluded_from_generic_long_text_renderer():
    source = SETTINGS.read_text(encoding="utf-8")

    assert "if (item.key === 'sandbox_docker_base_image') return false" in source


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


def test_docker_prebuild_uses_sse_and_keeps_build_failure_details_visible():
    source = SETTINGS.read_text(encoding="utf-8")

    assert "/api/v1/admin/sandbox/docker/prebuild/stream" in source
    assert "response.body?.getReader()" in source
    assert "dockerPrebuildLogs" in source
    assert "dockerPrebuildError" in source
    assert "复制构建日志" in source


def test_docker_prebuild_shows_elapsed_seconds_while_building():
    source = SETTINGS.read_text(encoding="utf-8")

    assert "dockerPrebuildElapsedSeconds" in source
    assert "预构建中 {{ dockerPrebuildElapsedSeconds }}s" in source
    assert "setInterval" in source


def test_docker_prebuild_log_panel_can_collapse_and_follows_new_logs():
    source = SETTINGS.read_text(encoding="utf-8")

    assert "dockerPrebuildLogsExpanded" in source
    assert "收起构建日志" in source
    assert "展开构建日志" in source
    assert "dockerPrebuildLogContainer" in source
    assert "container.scrollTop = container.scrollHeight" in source
