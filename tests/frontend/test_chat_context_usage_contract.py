from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.no_infrastructure


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_chat_input_exposes_context_usage_indicator_and_both_chat_surfaces_refresh_it():
    chat_input = _read("frontend/src/components/embed/ChatInput.vue")
    composable = _read("frontend/src/composables/useContextUsage.ts")
    embed_chat = _read("frontend/src/views/EmbedChat.vue")
    agent_debug = _read("frontend/src/views/AgentDebug.vue")
    input_box = chat_input[chat_input.index("<!-- Input Box -->"):]

    assert "contextUsage" in chat_input
    assert "请求输入上限" in chat_input
    assert 'data-testid="context-usage-indicator"' in chat_input
    assert 'data-testid="context-usage-details"' in chat_input
    assert 'data-testid="context-usage-bar"' not in input_box
    assert "'pr-24'" in input_box
    assert "contextUsageDetailsPlacement" in chat_input
    assert "bottom-[calc(100%+0.5rem)]" in chat_input
    assert "top-[calc(100%+0.5rem)]" in chat_input
    assert "contextUsagePercentLabel" in chat_input
    assert "{{ contextUsagePercentLabel }}" in chat_input
    assert "sandbox_policy" in composable
    assert "sandbox_runtime_env" in composable
    assert "sandboxPolicyLabel" in chat_input
    assert "sandboxRuntimeEnvLabel" in chat_input
    assert 'runtimeEnv === "docker"' in chat_input
    assert 'runtimeEnv === "host"' in chat_input
    assert 'return "平台 Docker 容器内"' in chat_input
    assert 'return "宿主机"' in chat_input
    assert '`local（${sandboxRuntimeEnvLabel.value}）`' in chat_input
    assert "Sandbox 策略" in chat_input
    assert "/api/v1/chat/conversation/" in composable
    assert "context-usage" in composable
    assert "useContextUsage" in embed_chat
    assert "useContextUsage" in agent_debug
    assert ':context-usage="contextUsage"' in embed_chat
    assert ':context-usage="contextUsage"' in agent_debug
