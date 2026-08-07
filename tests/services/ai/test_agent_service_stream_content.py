import pytest

from app.services.ai.agent_service import (
    _accumulate_reasoning_content,
    _accumulate_stream_content,
)


pytestmark = pytest.mark.no_infrastructure


def test_accumulate_stream_content_excludes_typed_reasoning_events():
    content = _accumulate_stream_content("回答", {
        "type": "reasoning_content",
        "content": "模型推理",
    })

    assert content == "回答"
    assert _accumulate_stream_content(content, {"content": "补充回答"}) == "回答补充回答"


def test_accumulate_reasoning_content_is_stored_separately():
    assert _accumulate_reasoning_content("", {
        "type": "reasoning_content",
        "content": "模型推理",
    }) == "模型推理"
    assert _accumulate_reasoning_content("模型推理", {"content": "回答"}) == "模型推理"
