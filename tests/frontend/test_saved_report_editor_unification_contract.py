from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.no_infrastructure


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_ai_surfaces_use_data_portal_report_editor():
    for path in ("frontend/src/views/EmbedChat.vue", "frontend/src/views/AgentDebug.vue"):
        source = _read(path)
        assert "import DataPortalReportCreateModal" in source
        assert "<DataPortalReportCreateModal" in source
        assert ':report="saveReportForm"' in source
        assert '@created="handleSavedReportEditorCreated"' in source
        assert "<SavedReportEditorModal" not in source


def test_shared_report_editor_accepts_ai_draft_and_keeps_context_read_only():
    source = _read("frontend/src/components/data-portal/DataPortalReportCreateModal.vue")

    assert "initialDraft?: any | null" in source
    assert "overlayClass?: string" in source
    assert "overlayStyle?: Record<string, string>" in source
    assert "scrollbarVariant?: 'embed' | 'debug'" in source
    assert "original_query" in source
    assert "来源提问" in source
    assert "activeReport" in source


def test_dynamic_sql_trial_asks_for_parameters_before_querying():
    source = _read("frontend/src/components/data-portal/DataPortalReportCreateModal.vue")

    assert "showTestParameterModal" in source
    assert "testParameterForm" in source
    assert "openTestParameterModal" in source
    assert "custom_range" in source
    assert "custom_month_range" in source
    assert "确认试跑" in source
