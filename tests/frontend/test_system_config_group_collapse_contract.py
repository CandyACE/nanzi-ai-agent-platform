"""SystemConfig 配置分组折叠与批量展开/收起契约。"""

from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure
ROOT = Path(__file__).resolve().parents[2]
SYSTEM_CONFIG = ROOT / "frontend/src/views/SystemConfig.vue"


def test_system_config_groups_support_individual_and_global_collapse_controls():
    source = SYSTEM_CONFIG.read_text(encoding="utf-8")

    assert "collapsedConfigGroups" in source
    assert "toggleConfigGroup" in source
    assert "expandAllConfigGroups" in source
    assert "collapseAllConfigGroups" in source
    assert "全部展开" in source
    assert "全部折叠" in source
    assert "aria-expanded" in source
    assert "isConfigGroupCollapsed(String(category))" in source
