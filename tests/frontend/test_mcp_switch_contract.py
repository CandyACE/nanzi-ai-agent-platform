from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure

SOURCE = Path("frontend/src/components/Switch.vue").read_text()


def test_switch_exposes_loading_state_and_spinner():
    assert "loading?: boolean" in SOURCE
    assert ":disabled=\"disabled || loading\"" in SOURCE
    assert "animate-spin" in SOURCE
    assert "aria-busy" in SOURCE
