from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure
ROOT = Path(__file__).resolve().parents[2]
SETTINGS = ROOT / "frontend/src/views/SystemConfig.vue"


def test_ssh_auth_type_is_a_two_option_select_with_dependent_credentials():
    source = SETTINGS.read_text(encoding="utf-8")

    assert "sandboxSshAuthType" in source
    assert "sandbox_ssh_auth_type" in source
    assert '<option value="password">' in source
    assert '<option value="key">' in source
    assert "sandbox_ssh_password" in source
    assert "sandbox_ssh_private_key" in source
    assert "private_key" in source
    assert "sandboxSshAuthType.value === 'key'" in source
    assert "sandboxSshAuthType.value !== 'key'" in source
