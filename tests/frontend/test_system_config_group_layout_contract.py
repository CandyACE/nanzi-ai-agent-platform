from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure
SYSTEM_CONFIG = Path(__file__).resolve().parents[2] / "frontend/src/views/SystemConfig.vue"


def test_embedding_config_rows_form_one_continuous_group():
    source = SYSTEM_CONFIG.read_text(encoding="utf-8")

    assert "embed-config-group rounded-t-xl" in source
    assert "embed-config-group border-x" in source
    assert "embed-config-group rounded-b-xl" in source
    assert "embed-config-group bg-indigo-50/30 rounded-lg" not in source
    assert "!mt-0" in source
