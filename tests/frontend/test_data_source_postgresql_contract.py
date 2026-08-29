from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure


ROOT = Path(__file__).parents[2]


def test_data_source_management_exposes_postgresql_option():
    source = (ROOT / "frontend/src/views/DataSourceManagement.vue").read_text()

    assert "postgresql" in source
    assert "PostgreSQL" in source
    assert "defaultPort: 5432" in source
    assert "@input=\"sanitizeNameSuffix\"" in source
    assert "@paste=\"handleNamePaste\"" in source
    assert "replace(/[^a-zA-Z0-9_]/g, '')" in source


def test_smart_import_passes_selected_data_source_to_metric_generation():
    """智能导入分析请求必须携带所选数据源，确保 PostgreSQL 指标按正确方言生成。"""
    api_source = (ROOT / "frontend/src/api/metadata.ts").read_text()
    wizard_source = (ROOT / "frontend/src/components/metadata/SmartImportWizard.vue").read_text()
    modal_source = (ROOT / "frontend/src/components/metadata/DatabaseImportModal.vue").read_text()

    assert "analyzeDDL: (ddl: string, dataSource?: string)" in api_source
    assert "data_source: dataSource" in api_source
    assert "metadataApi.analyzeDDL(ddlText.value, analysisDataSource || undefined)" in wizard_source
    assert "{ id: 'postgresql', name: 'PostgreSQL'" in modal_source
