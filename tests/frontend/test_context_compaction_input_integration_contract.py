from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.no_infrastructure


@pytest.mark.parametrize(
    "relative_path",
    ["frontend/src/views/EmbedChat.vue", "frontend/src/views/AgentDebug.vue"],
)
def test_chat_surfaces_wire_compaction_state_into_input_and_refresh_after_send(relative_path):
    source = (ROOT / relative_path).read_text(encoding="utf-8")

    assert "useContextCompactions" in source
    assert "contextCompactionCount" in source
    assert "contextCompactions" in source
    assert "contextCompactionsLoading" in source
    assert "contextCompactionsError" in source
    assert ':context-compaction-count="contextCompactionCount"' in source
    assert ':context-compaction-records="contextCompactions"' in source
    assert ':context-compaction-loading="contextCompactionsLoading"' in source
    assert ':context-compaction-error="contextCompactionsError"' in source
    assert "refreshContextCompactions" in source
    assert "@refresh-context-compactions" in source


def test_embed_chat_passes_embed_auth_headers_to_compaction_query():
    source = (ROOT / "frontend/src/views/EmbedChat.vue").read_text(encoding="utf-8")

    assert "headers: embedAuthHeaders()" in source
