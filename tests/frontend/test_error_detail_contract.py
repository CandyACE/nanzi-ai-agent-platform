from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.no_infrastructure


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_error_detail_card_is_collapsed_safe_text_and_copyable():
    source = _source("frontend/src/components/chat/ErrorDetailCard.vue")

    assert "defineProps" in source
    assert "<details" in source
    assert 'v-if="rawError"' in source
    assert "<summary" in source
    assert "查看技术详情" in source
    assert "{{ rawError }}" in source
    assert "copyToClipboard" in source
    assert "@click.prevent.stop" in source
    assert "<details open" not in source


def test_both_chat_surfaces_use_shared_error_presentation_and_detail_card():
    for path in ("frontend/src/views/EmbedChat.vue", "frontend/src/views/AgentDebug.vue"):
        source = _source(path)
        assert "ErrorDetailCard" in source
        assert "applyStreamErrorMessage" in source
        assert "StreamErrorDetail" in source
        assert "errorDetail" in source
        assert "> ❌ **服务异常**" not in source
        assert "> 服务异常: " not in source


def test_error_detail_card_is_rendered_after_main_message_content():
    for path in ("frontend/src/views/EmbedChat.vue", "frontend/src/views/AgentDebug.vue"):
        source = _source(path)
        renderer_at = source.find("<MessageRenderer")
        detail_at = source.find("<ErrorDetailCard")
        assert renderer_at >= 0
        assert detail_at > renderer_at
        assert "msg.errorDetail?.rawError" in source


def test_tool_error_reason_is_carried_to_the_execution_timeline():
    handlers = _source("frontend/src/utils/agentscopeSseHandlers.ts")
    timeline = _source("frontend/src/utils/processTimeline.ts")
    component = _source("frontend/src/components/chat/ChatExecutionTimeline.vue")

    assert "error_reason" in handlers
    assert "error_reason" in timeline
    assert "error_reason" in component
    assert "错误原因：" in component
