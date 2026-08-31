from datetime import datetime

import pytest

from app.schemas.agent import AgentExecutionStep
from app.services.ai import audit


pytestmark = pytest.mark.no_infrastructure


class _Session:
    def __init__(self):
        self.rows = []

    def add_all(self, rows):
        self.rows.extend(rows)

    async def commit(self):
        return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None


@pytest.mark.asyncio
async def test_trace_persistence_bounds_copy_without_mutating_runtime_step(monkeypatch):
    session = _Session()
    source_output = {"content": "结果" * 20_000}
    step = AgentExecutionStep(
        step_number=1,
        event_type="tool_call",
        tool_name="read",
        tool_output=source_output,
        timestamp=datetime.now(),
    )
    monkeypatch.setattr(audit, "AsyncSessionLocal", lambda: session)

    await audit.AuditManager.save_trace_logs("trace-1", [step])

    assert step.tool_output is source_output
    assert len(session.rows) == 1
    persisted = session.rows[0].tool_output
    assert persisted["__audit_trace"]["truncated"] is True
    assert persisted["__audit_trace"]["original_bytes"] > 64 * 1024
