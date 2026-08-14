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


def test_accumulate_stream_content_promotes_process_narration_only():
    content = _accumulate_stream_content("", {
        "type": "process_narration",
        "content": "I'll search first.",
    })
    assert content == ""
    content = _accumulate_stream_content(content, {
        "type": "process_narration_commit",
        "content": "I'll search first.",
    })
    assert content == ""
    content = _accumulate_stream_content(content, {
        "type": "answer_delta",
        "content": "最终报告",
    })
    assert content == "最终报告"
    assert _accumulate_stream_content(content, {"content": "补充"}) == "最终报告补充"


def test_accumulate_stream_content_retracts_speculative_body():
    content = _accumulate_stream_content("", {"content": "让我再搜一次。"})
    assert content == "让我再搜一次。"
    content = _accumulate_stream_content(content, {
        "type": "retraction",
        "content": "",
        "final": False,
    })
    assert content == ""
    content = _accumulate_stream_content(content, {
        "type": "process_narration_commit",
        "content": "让我再搜一次。",
    })
    assert content == ""
    content = _accumulate_stream_content(content, {"content": "最终报告"})
    assert content == "最终报告"


def test_accumulate_stream_content_retracts_typed_answer_delta():
    content = _accumulate_stream_content("", {
        "type": "answer_delta",
        "content": "先查一下",
    })
    assert content == "先查一下"
    content = _accumulate_stream_content(content, {
        "type": "retraction",
        "content": "",
        "final": False,
    })
    assert content == ""
    content = _accumulate_stream_content(content, {
        "type": "answer_delta",
        "content": "最终报告",
    })
    assert content == "最终报告"


def test_chat_turn_persists_finalized_process_timeline_with_memory_and_audit():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[3] / "app/services/ai/agent_service.py").read_text(
        encoding="utf-8"
    )
    assert "apply_stream_chunk" in source
    assert "finalize_process_timeline" in source
    assert "process_timeline=" in source


def test_accumulate_reasoning_content_is_stored_separately():
    assert _accumulate_reasoning_content("", {
        "type": "reasoning_content",
        "content": "模型推理",
    }) == "模型推理"
    assert _accumulate_reasoning_content("模型推理", {"content": "回答"}) == "模型推理"
