import pytest

from app.services.ai.agent_service import _apply_turn_status_signal


def _resolve(chunks):
    status = "success"
    for chunk in chunks:
        status = _apply_turn_status_signal(status, chunk)
    return status


@pytest.mark.no_infrastructure
def test_step_level_tool_failure_log_does_not_fail_the_turn():
    status = _resolve([
        {"type": "log", "title": "工具完成: bash (120ms)", "status": "error"},
        {"content": "开源项目 Star 日报已生成"},
        {"type": "log", "title": "工具完成: send_portal_notification", "status": "success"},
    ])

    assert status == "success"


@pytest.mark.no_infrastructure
def test_mid_stream_error_is_overridden_by_final_answer():
    status = _resolve([
        {"content": "[系统错误] 工具调用失败", "status": "error"},
        {"content": "重试后已取到完整数据"},
    ])

    assert status == "success"


@pytest.mark.no_infrastructure
def test_terminal_error_still_fails_the_turn():
    status = _resolve([
        {"content": "正在汇总"},
        {"type": "error", "status": "error", "content": "模型调用失败"},
    ])

    assert status == "error"


@pytest.mark.no_infrastructure
def test_awaiting_states_are_not_overridden_by_trailing_content():
    assert _resolve([
        {"type": "permission_required", "content": "需要确认"},
        {"content": "已暂停，等待确认"},
    ]) == "awaiting_permission"

    assert _resolve([
        {"type": "external_execution_required", "status": "pending", "content": "需要外部执行"},
        {"content": "已暂停，等待外部执行"},
    ]) == "awaiting_external_execution"


@pytest.mark.no_infrastructure
def test_auxiliary_chunks_keep_current_status():
    assert _resolve([
        {"trace_id": "trace-1", "status": "init"},
        {"type": "meta", "prompt_tokens": 10},
        {"type": "retraction", "content": ""},
    ]) == "success"
