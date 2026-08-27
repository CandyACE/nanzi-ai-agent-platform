from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_shared_sse_dispatcher_handles_and_prepends_model_fallback_notice():
    source = _read("frontend/src/utils/agentscopeSseHandlers.ts")

    assert "fallbackNotice?: string" in source
    assert 'case "model_fallback"' in source
    assert "主模型" in source
    assert "fallback 模型" in source
    assert "msg.content =" in source
    assert 'status: "warning"' in source
    assert 'const replacement = String(data.content ?? "")' in source
    assert "replacement.startsWith(msg.fallbackNotice)" in source


def test_both_chat_surfaces_use_shared_fallback_dispatcher():
    for path in ("frontend/src/views/EmbedChat.vue", "frontend/src/views/AgentDebug.vue"):
        assert "dispatchAgentscopeStreamEvent" in _read(path)
