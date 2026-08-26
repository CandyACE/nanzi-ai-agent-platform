"""契约：元数据数据集列表默认优先显示已启用数据集。"""

from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "frontend/src/views/MetadataDatasets.vue").read_text(encoding="utf-8")


def test_dataset_sort_prioritizes_enabled_items_before_secondary_sort():
    sort_logic = SOURCE[SOURCE.index("const compareDatasets"):SOURCE.index("const displayDatasets")]

    assert "const statusPriority = Number(b.status === 1) - Number(a.status === 1)" in sort_logic
    assert "if (sortField.value !== 'status')" in sort_logic
    assert "if (statusPriority !== 0) return statusPriority" in sort_logic
    assert "return [...list].sort(compareDatasets)" in SOURCE
