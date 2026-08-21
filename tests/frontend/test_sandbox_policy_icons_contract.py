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


def test_docker_policy_is_disabled_when_platform_runs_in_docker():
    source = SETTINGS.read_text(encoding="utf-8")

    assert "disabled: runtimeEnv.value === 'docker'" in source
    assert ":disabled=\"isConfigItemDisabled(String(category), item) || opt.disabled\"" in source
    assert "禁止嵌套 Docker 沙箱" in source
