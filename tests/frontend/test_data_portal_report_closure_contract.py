from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.no_infrastructure


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_drawer_report_panel_is_not_hidden_by_dataset_container():
    source = _read("frontend/src/components/chatbi/DatasetCapabilityMenu.vue")
    report_marker = "<!-- 固化报表 Tab 专属面板 -->"
    dataset_wrappers = "<div v-show=\"menuActiveTab === 'datasets'\""

    assert source.count(dataset_wrappers) == 2
    first_dataset_end = source.index("</div>", source.index(dataset_wrappers))
    report_start = source.index(report_marker)
    second_dataset_start = source.index(dataset_wrappers, report_start)
    assert first_dataset_end < report_start < second_dataset_start
    assert "import DataPortalReportCreateModal" in source


def test_report_creation_uses_safe_source_options_and_shared_preview_contract():
    modal = _read("frontend/src/components/data-portal/DataPortalReportCreateModal.vue")

    assert "report?: any | null" in modal
    assert "/api/portal/saved-reports/source-options" in modal
    assert "/api/portal/metadata/datasets/accessible" in modal
    assert "/api/portal/saved-reports/preview-sql" in modal
    assert "sql-preview" not in modal
    assert "source_type" in modal
    assert "selectedDataSourceName" in modal
    assert "testPassed" in modal
    assert "watch(" in modal
    assert "!testPassed" in modal


def test_report_creation_shows_dataset_display_name_with_physical_name():
    modal = _read("frontend/src/components/data-portal/DataPortalReportCreateModal.vue")

    assert "formatDatasetLabel" in modal
    assert "{{ formatDatasetLabel(ds) }}" in modal
    assert "display_name" in modal


def test_report_creation_supports_dynamic_parameter_shortcuts_and_parameterized_save():
    modal = _read("frontend/src/components/data-portal/DataPortalReportCreateModal.vue")

    assert "sqlEditor" in modal
    assert "insertSqlFragment" in modal
    assert "showSqlHelp" in modal
    assert "aria-label=\"查看动态参数 SQL 写法说明\"" in modal
    for placeholder in (
        "{{start_date}}",
        "{{end_date}}",
        "{{start_datetime}}",
        "{{end_datetime}}",
        "{{start_month}}",
        "{{end_month}}",
    ):
        assert placeholder in modal
    assert "buildPreviewSql" in modal
    assert "mode: parameterSchema.length ? 'param_sql' : 'static_sql'" in modal
    assert "sql_template: parameterSchema.length ? sqlContent : undefined" in modal
    assert "params_schema: parameterSchema" in modal
    assert "default_params: defaultParams" in modal
    assert "report?.sql_template || report?.sql_content" in modal
    assert "preserveExistingParameterConfig" in modal
    assert "props.report?.default_params" in modal


def test_report_creation_supports_configuring_custom_parameters():
    modal = _read("frontend/src/components/data-portal/DataPortalReportCreateModal.vue")

    assert "customParameterConfigs" in modal
    assert "插入自定义参数" in modal
    assert "type === 'select'" in modal or 'type === "select"' in modal
    assert "options" in modal


def test_personal_data_portal_renders_reports_independently_and_exposes_management_actions():
    composable = _read("frontend/src/composables/useDataPortalHome.ts")
    page = _read("frontend/src/views/DataPortalHome.vue")
    section = _read("frontend/src/components/data-portal/DataPortalReportSection.vue")

    assert "reportsLoading" in composable
    assert "activeSection === 'reports'" in page
    assert ":manage=\"true\"" in page
    assert "editingReport" in page
    assert 'openReportAt(report, "info", undefined, true)' in page
    assert 'run_now: "1"' in page
    assert 'openReportAt(report, "subscription")' in page
    assert 'report_detail_tab: detailTab' in page
    assert "SavedReportItemCard" in section
    for event in ("favorite", "pin", "copy", "delete", "edit", "subscription"):
        assert f'event: "{event}"' in section


def test_report_center_supports_keyword_search_and_pagination():
    section = _read("frontend/src/components/data-portal/DataPortalReportSection.vue")

    assert "searchQuery" in section
    assert "currentPage" in section
    assert "pageSize" in section
    assert "pagedReports" in section
    assert "上一页" in section
    assert "下一页" in section


def test_report_source_api_never_uses_metadata_connection_password_payload():
    modal = _read("frontend/src/components/data-portal/DataPortalReportCreateModal.vue")
    assert "/api/portal/metadata/db/connection-configs" not in modal
    assert "password" not in modal
