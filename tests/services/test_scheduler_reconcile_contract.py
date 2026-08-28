from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure
ROOT = Path(__file__).resolve().parents[2]


def test_enabled_scheduler_reconciles_database_tasks_for_api_only_nodes():
    scheduler = (ROOT / "app/services/ai/scheduler_service.py").read_text(encoding="utf-8")

    assert "SCHEDULER_RECONCILE_INTERVAL_SEC = 30" in scheduler
    assert "IntervalTrigger(seconds=SCHEDULER_RECONCILE_INTERVAL_SEC" in scheduler
    assert 'id="system_scheduler_reconcile"' in scheduler
    assert "async def _system_scheduler_reconcile_job" in scheduler
    assert "await scheduler_service.reload_tasks()" in scheduler
    assert "await scheduler_service.reload_saved_report_subscriptions()" in scheduler
    assert "active_task_ids" in scheduler
    assert "active_subscription_ids" in scheduler
