from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.no_infrastructure


def test_watchdog_uses_per_message_agent_toolcall_timeout_snapshot():
    handlers = (ROOT / "frontend/src/utils/agentscopeSseHandlers.ts").read_text(encoding="utf-8")
    embed = (ROOT / "frontend/src/views/EmbedChat.vue").read_text(encoding="utf-8")
    debug = (ROOT / "frontend/src/views/AgentDebug.vue").read_text(encoding="utf-8")

    assert "agentMaxToolcallTimeoutSeconds" in handlers
    assert "DEFAULT_AGENT_MAX_TOOLCALL_TIMEOUT_SECONDS = 180" in handlers
    assert 'case "run_config":' in handlers
    assert "resolveAgentMaxToolcallTimeoutMs(msg)" in handlers
    assert "staleMs = 120_000" not in handlers
    assert "startStalePendingTimer(agentMsg.value)" in embed
    assert "markStalePendingStreamLogs(msg)" in embed
    assert "markStalePendingStreamLogs(agentMsg.value)" in debug
