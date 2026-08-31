from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.no_infrastructure


def test_trace_viewer_does_not_eagerly_expand_truncated_outputs():
    source = (ROOT / "frontend/src/components/TraceLogViewer.vue").read_text(encoding="utf-8")

    assert "step.tool_output?.__audit_trace?.truncated" in source
    assert "expandedSteps.value[`output-${idx}`] = !" in source


def test_trace_endpoints_apply_audit_payload_bound_before_returning_results():
    portal = (ROOT / "app/api/portal/endpoints/audit.py").read_text(encoding="utf-8")
    chat = (ROOT / "app/api/v1/endpoints/chat.py").read_text(encoding="utf-8")

    assert portal.count("bound_audit_payload") >= 4
    assert "tool_output=bound_audit_payload(row.tool_output)" in chat


def test_full_tabular_consumers_prefer_the_session_result_cache():
    export_service = (ROOT / "app/services/ai/export_service.py").read_text(encoding="utf-8")
    notification = (ROOT / "app/services/task_notification_delivery.py").read_text(encoding="utf-8")

    assert "get_current_data_result" in export_service
    assert 'cached.get("trace_id")' in export_service
    assert "get_current_data_result" in notification
    assert 'cached.get("trace_id")' in notification
