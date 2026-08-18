from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.no_infrastructure
@pytest.mark.parametrize(
    "relative_path",
    [
        "frontend/src/views/EmbedChat.vue",
        "frontend/src/views/AgentDebug.vue",
    ],
)
def test_edit_resend_uses_only_real_chat_messages(relative_path: str):
    source = (ROOT / relative_path).read_text(encoding="utf-8")

    assert "const isChatContextMessage" in source
    assert "message.role === \"user\" || message.role === \"agent\"" in source
    assert "messages.value.filter(isChatContextMessage)" in source
    assert "remainingMessages.filter(isChatContextMessage)" in source


@pytest.mark.no_infrastructure
@pytest.mark.parametrize(
    "relative_path",
    [
        "frontend/src/views/EmbedChat.vue",
        "frontend/src/views/AgentDebug.vue",
    ],
)
def test_edit_resend_stops_when_server_history_cannot_be_truncated(relative_path: str):
    source = (ROOT / relative_path).read_text(encoding="utf-8")

    assert "const truncateServerHistory = async" in source
    assert "if (!(await truncateServerHistory(keepCount))) return;" in source
