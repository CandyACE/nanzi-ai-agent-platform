from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure
ROOT = Path(__file__).resolve().parents[2]


def test_runners_consume_agent_service_context_without_second_hard_truncation():
    assistant = (
        ROOT / "app/services/ai/runners/assistant_agent_runner.py"
    ).read_text(encoding="utf-8")
    knowledge = (
        ROOT / "app/services/ai/runners/knowledge_agent_runner.py"
    ).read_text(encoding="utf-8")

    assert "history[-20:]" not in assistant
    assert "history[-10:]" not in knowledge


def test_context_observability_exposes_physical_window_and_history_budget():
    middleware = (
        ROOT / "app/services/ai/runtime/agentscope/middleware.py"
    ).read_text(encoding="utf-8")
    session_status = (
        ROOT / "app/services/ai/tools/session_status.py"
    ).read_text(encoding="utf-8")

    assert '"physical_window"' in middleware
    assert '"history_budget"' in middleware
    assert '"physical_window"' in session_status
    assert '"history_budget"' in session_status
