import pytest

from app.services.ai.runtime.agentscope.text_sanitize import (
    sanitize_assistant_stream_text,
    strip_model_reasoning_from_answer,
)

pytestmark = pytest.mark.no_infrastructure


def test_sanitize_strips_think_blocks():
    raw = f"<{'think'}>hidden</{'think'}>可见正文"
    assert sanitize_assistant_stream_text(raw) == "可见正文"


def test_sanitize_strips_function_calls():
    raw = '<function_calls><invoke name="Bash"/></function_calls>回答'
    assert sanitize_assistant_stream_text(raw) == "回答"


def test_strip_model_reasoning_removes_embedchat_reasoning_panel_leak():
    reasoning = "逐步推演：先查 schema，再写 SQL，最后解读。"
    content = f"{reasoning}\n\n结论：本月活跃用户上升。"
    cleaned = strip_model_reasoning_from_answer(content, reasoning_content=reasoning)
    assert "逐步推演" not in cleaned
    assert "结论：本月活跃用户上升。" in cleaned


def test_strip_taskcenter_delivery_meta_from_user_facing_answer():
    raw = (
        "三、关键提示\n"
        "优先选 G28。\n\n"
        "由于任务指令要求将结果发送到站内消息，但根据【结果通知说明】，"
        "任务结束后将由 TaskCenter 统一投递结果，我无需也不应调用 send_portal_notification "
        "等通知工具。因此以上分析结论即为本轮完整交付内容，将由系统统一投递至站内消息。"
    )
    cleaned = strip_model_reasoning_from_answer(raw)
    assert "send_portal_notification" not in cleaned
    assert "结果通知说明" not in cleaned
    assert "统一投递" not in cleaned
    assert "优先选 G28。" in cleaned
