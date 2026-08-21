from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.no_infrastructure


def test_context_compactions_composable_has_request_safe_shared_state_contract():
    source = (ROOT / "frontend/src/composables/useContextCompactions.ts").read_text(
        encoding="utf-8",
    )

    assert "useContextCompactions" in source
    assert "ContextCompactionRecord" in source
    assert "contextCompactions" in source
    assert "contextCompactionCount" in source
    assert "refreshContextCompactions" in source
    assert "latestRequestId" in source
    assert "requestId !== latestRequestId" in source
    assert "conversationId" in source
    assert "headers" in source
    assert "getContextCompactions" in source
    assert "contextCompactionsError" in source
    assert "Array.isArray(records)" in source
