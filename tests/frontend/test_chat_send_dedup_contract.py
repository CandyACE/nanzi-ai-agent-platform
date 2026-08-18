from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.no_infrastructure


def _assert_send_lock_contract(source: str) -> None:
    wrapper_start = source.index("const sendMessage = async () => {")
    internal_start = source.index("const sendMessageInternal = async () => {", wrapper_start)
    wrapper = source[wrapper_start:internal_start]

    assert "const sendInFlight = ref(false);" in source[:wrapper_start]
    assert "if (sendInFlight.value) return;" in wrapper
    assert "sendInFlight.value = true;" in wrapper
    assert "return await sendMessageInternal();" in wrapper
    assert "finally" in wrapper
    assert "sendInFlight.value = false;" in wrapper
    assert wrapper.index("sendInFlight.value = true;") < wrapper.index("await sendMessageInternal();")


def test_chat_surfaces_lock_duplicate_sends_before_async_preflight_finishes():
    for relative_path in (
        "frontend/src/views/EmbedChat.vue",
        "frontend/src/views/AgentDebug.vue",
    ):
        source = (ROOT / relative_path).read_text(encoding="utf-8")
        _assert_send_lock_contract(source)
        assert ':is-processing="isProcessing || sendInFlight"' in source
