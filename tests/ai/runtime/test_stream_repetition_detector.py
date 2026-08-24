from __future__ import annotations

import pytest
from types import SimpleNamespace

from app.services.ai.runtime.stream_repetition_detector import (
    StreamRepetitionDetector,
    RepetitionVerdict,
)
from app.services.ai.runtime.agentscope.process_narration import (
    on_text_delta,
    on_model_call_start,
    on_tool_call_start,
)
from app.services.ai.runners.chatbi.react_stream import stream_agentscope_events
from app.services.ai.runners.chatbi.run_state import DataRunState


pytestmark = pytest.mark.no_infrastructure


def test_detector_normal_output_not_fused():
    detector = StreamRepetitionDetector(threshold=3)
    text_chunks = [
        "你好，我正在为您查询数据。",
        "数据查询已完成，共找到 10 条记录。",
        "接下来我将为您生成统计图表。",
    ]
    for chunk in text_chunks:
        verdict = detector.feed(chunk)
        assert verdict.fused is False
    assert detector.is_fused is False


def test_detector_fuses_on_consecutive_repeated_sentences():
    detector = StreamRepetitionDetector(threshold=3)
    phrase = "让我查看一下聊天区域的实际内容，看看输入框在哪里。"

    # 第 1 遍
    v1 = detector.feed(phrase + "\n")
    assert v1.fused is False
    assert detector.is_fused is False

    # 第 2 遍
    v2 = detector.feed(phrase + "\n")
    assert v2.fused is False
    assert detector.is_fused is False

    # 第 3 遍：触发熔断
    v3 = detector.feed(phrase + "\n")
    assert v3.fused is True
    assert "让我查看一下聊天区域的实际内容" in v3.repeated_phrase
    assert v3.repeat_count >= 3
    assert detector.is_fused is True

    # 熔断后继续 feed 依然返回熔断状态
    v4 = detector.feed("额外文本")
    assert v4.fused is True


def test_default_detector_waits_until_fiftieth_repeated_sentence():
    detector = StreamRepetitionDetector()
    phrase = "让我查看一下聊天区域的实际内容，看看输入框在哪里。"

    for repetition in range(49):
        verdict = detector.feed(phrase + "\n")
        assert verdict.fused is False, f"unexpected fuse at repetition {repetition + 1}"

    verdict = detector.feed(phrase + "\n")

    assert verdict.fused is True
    assert verdict.repeat_count >= 50
    assert detector.is_fused is True


def test_detector_stream_incremental_deltas():
    detector = StreamRepetitionDetector(threshold=3)
    sentence = "正在处理任务请稍候。"

    # 模拟流式一个字一个字推送
    for _ in range(3):
        for char in sentence:
            detector.feed(char)
        detector.feed("\n")

    assert detector.is_fused is True


def test_detector_ignores_repeated_text_without_sentence_terminator():
    detector = StreamRepetitionDetector(threshold=3, min_phrase_len=6)
    # 无句末标点的连续重复字符串不属于句子，不参与熔断判断
    unit = "正在检索相关数据文档"

    for _ in range(100):
        verdict = detector.feed(unit)

    assert verdict.fused is False
    assert detector.is_fused is False


def test_detector_ignores_repeated_markdown_table_separator():
    detector = StreamRepetitionDetector(threshold=3)
    table_separator = "|----|----|----|----|----|\n"

    for _ in range(100):
        verdict = detector.feed(table_separator)

    assert verdict.fused is False
    assert detector.is_fused is False


def test_detector_ignores_short_common_words():
    detector = StreamRepetitionDetector(threshold=3, min_phrase_len=6)
    # 简短词汇（如“好的”、“是的”）不应误触发熔断
    for _ in range(5):
        verdict = detector.feed("好的。\n")
        assert verdict.fused is False
    assert detector.is_fused is False


def test_detector_does_not_bridge_short_intervening_phrase():
    detector = StreamRepetitionDetector(threshold=3, min_phrase_len=6)
    phrase = "请帮我检查当前聊天页面的输入框位置。"

    verdict = detector.feed(f"{phrase}\n好的。\n{phrase}\n{phrase}\n")

    assert verdict.fused is False
    assert detector.is_fused is False


def test_detector_reset():
    detector = StreamRepetitionDetector(threshold=3)
    phrase = "让我查看一下聊天区域的实际内容。\n"

    detector.feed(phrase)
    detector.feed(phrase)
    assert detector.is_fused is False

    # 中途重置（如执行了工具或新一轮思考）
    detector.reset()
    assert detector.is_fused is False

    # 再次输入 2 次不会熔断
    detector.feed(phrase)
    detector.feed(phrase)
    assert detector.is_fused is False

    # 第 3 次熔断
    v = detector.feed(phrase)
    assert v.fused is True


def test_process_narration_repetition_interception():
    state = {}
    phrase = "让我查看一下聊天区域的实际内容，看看输入框在哪里。\n"

    # 前 49 遍不熔断
    for repetition in range(49):
        events = on_text_delta(state, phrase)
        assert len(events) == 1
        assert events[0]["type"] == "process_narration", repetition + 1

    # 第 50 遍：触发熔断并返回 error 告警事件
    events50 = on_text_delta(state, phrase)
    assert len(events50) == 1
    assert events50[0]["type"] == "error"
    assert "流式安全拦截" in events50[0]["content"]
    assert state.get("repetition_fused") is True

    # 第 51 遍：已被熔断，后续增量直接被丢弃（返回空列表）
    events51 = on_text_delta(state, phrase)
    assert events51 == []

    # 开启新一轮调用后重置
    on_model_call_start(state)
    assert state.get("repetition_detector").is_fused is False


@pytest.mark.asyncio
async def test_chatbi_stream_resets_repetition_detector_for_each_stream():
    class FakeRunner:
        _execution_backend = None

        def __init__(self):
            self._last_run_state = None
            self.trace_buffer = []
            self.step_counter = 0
            self.config = SimpleNamespace(agent_name="DataAgent", model_name="fake", temperature=0)

        def _build_stream_state(self, state, stream_meta):
            return {}

        def _sync_pending_data_run_state(self, state, pending_state):
            return None

        def _runtime_agent_name(self):
            return "DataAgent"

        def _has_sql_plan(self, text):
            return False

        def _increment_step(self):
            self.step_counter += 1

    async def collect(runner, state, count):
        async def events():
            for _ in range(count):
                yield SimpleNamespace(
                    type="TEXT_BLOCK_DELTA",
                    block_id="answer",
                    delta="让我查看一下聊天区域的实际内容，看看输入框在哪里。\n",
                )

        return [
            chunk
            async for chunk in stream_agentscope_events(
                runner,
                event_stream=events(),
                tools=[],
                native_model=SimpleNamespace(model="fake"),
                state=state,
                emit_final_guard=False,
            )
        ]

    runner = FakeRunner()
    state = DataRunState(requires_fresh_data=False)

    await collect(runner, state, 2)
    second_stream_chunks = await collect(runner, state, 1)

    assert not any(chunk.get("type") == "error" for chunk in second_stream_chunks)
