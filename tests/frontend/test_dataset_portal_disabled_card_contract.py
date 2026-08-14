from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.no_infrastructure


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_dataset_capability_menu_marks_and_disables_unenabled_cards():
    source = _source("frontend/src/components/chatbi/DatasetCapabilityMenu.vue")
    assert "enabled?: boolean" in source
    assert "isDatasetDisabled" in source
    assert "未启用" in source
    assert "数据集未启用，暂不可查询" in source
    assert 'v-if="!isDatasetDisabled(group)"' in source or ":disabled=\"isDatasetDisabled(group)\"" in source
    assert "if (isDatasetDisabled(group)) return" in source


def test_data_portal_home_sections_disable_unenabled_dataset_actions():
    scene = _source("frontend/src/components/data-portal/DataPortalSceneSection.vue")
    catalog = _source("frontend/src/components/data-portal/DataPortalCatalogSection.vue")
    types = _source("frontend/src/composables/useDatasetPortal.ts")
    assert "enabled?: boolean" in types
    assert "isDatasetDisabled" in scene
    assert "未启用" in scene
    assert "isDatasetDisabled" in catalog
    assert "未启用" in catalog
