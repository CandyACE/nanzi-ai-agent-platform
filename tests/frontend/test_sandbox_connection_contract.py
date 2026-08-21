from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure
ROOT = Path(__file__).resolve().parents[2]
SETTINGS = ROOT / "frontend/src/views/SystemConfig.vue"


def test_e2b_and_ssh_sections_expose_connection_test_buttons():
    source = SETTINGS.read_text(encoding="utf-8")

    assert "sandboxConnectionTesting" in source
    assert "testSandboxConnection" in source
    assert "/api/v1/admin/sandbox/${policy}/test-connection" in source
    assert "testSandboxConnection('e2b')" in source
    assert "testSandboxConnection('ssh')" in source
    assert "测试连接" in source
    assert "测试中..." in source
