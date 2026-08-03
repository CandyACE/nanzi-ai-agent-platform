from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.no_infrastructure


def test_sidebar_brand_text_stays_vertically_centered_with_logo():
    source = (ROOT / "frontend/src/views/Dashboard.vue").read_text(encoding="utf-8")

    assert 'class="h-16 flex items-center bg-sidebar' in source
    assert 'class="ml-2.5 flex flex-col justify-center"' in source
    assert "-translate-y-0.5" not in source
