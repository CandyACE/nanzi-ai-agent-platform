from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure
ROOT = Path(__file__).resolve().parents[2]
SETTINGS = ROOT / "frontend/src/views/SystemConfig.vue"


def test_sandbox_policy_options_render_semantic_icons_for_all_execution_modes():
    source = SETTINGS.read_text(encoding="utf-8")

    assert "ComputerDesktopIcon" in source
    assert "CubeIcon" in source
    assert "CloudIcon" in source
    assert "ServerIcon" in source
    assert "getSandboxPolicyIcon" in source
    assert ':is="getSandboxPolicyIcon(opt.value)"' in source
    assert 'aria-hidden="true"' in source


def test_docker_policy_is_available_when_platform_runs_in_docker():
    source = SETTINGS.read_text(encoding="utf-8")

    assert "value: 'docker'" in source
    assert "disabled: false" in source
    assert ":disabled=\"isConfigItemDisabled(String(category), item) || opt.disabled\"" in source
    assert "showToast('平台后端已经运行在 Docker 容器内，不能启用 docker 沙箱模式', 'warning')" not in source
