import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.services.ai.session_tool_artifact import (
    SESSION_ARTIFACT_BLOCK_MARKER,
    append_session_tool_artifact_to_system_prompt,
    artifact_candidate_score,
    build_artifact_payload,
    build_session_artifact_prompt_block,
    consider_turn_artifact_candidate,
    filter_tools_for_reusable_result,
    should_inject_session_artifact,
)

pytestmark = pytest.mark.no_infrastructure


def test_artifact_candidate_score_prefers_mcp_over_clock():
    long_text = "x" * 200
    mcp_score = artifact_candidate_score(
        tool_name="analytics_report",
        source_type="mcp",
        permission_scope="read",
        text=long_text,
        structured=None,
    )
    clock_score = artifact_candidate_score(
        tool_name="get_current_time",
        source_type="system",
        permission_scope="read",
        text=long_text,
        structured=None,
    )
    assert mcp_score > 0
    assert clock_score == 0


def test_todo_write_is_not_a_reusable_artifact_candidate():
    score = artifact_candidate_score(
        tool_name="todo_write",
        source_type="system",
        permission_scope="read",
        text="任务清单已更新",
        structured={"todos": [{"content": "继续执行", "status": "in_progress"}]},
    )

    assert score == 0


def test_consider_turn_artifact_keeps_highest_score_candidate():
    turn = {"user_question": "查报表", "trace_id": "t1", "best": None}
    small = {"rows": [{"a": 1}]}
    consider_turn_artifact_candidate(
        turn,
        tool_name="low_value",
        tool_args={},
        tool_output=json.dumps(small),
        source_type="static",
        permission_scope="read",
    )
    first_score = turn["best"]["_score"]
    consider_turn_artifact_candidate(
        turn,
        tool_name="mcp_report",
        tool_args={},
        tool_output="y" * 500,
        source_type="mcp",
        permission_scope="read",
    )
    assert turn["best"]["tool_name"] == "mcp_report"
    assert turn["best"]["_score"] >= first_score


def test_sub_agent_result_is_a_generic_reusable_candidate():
    turn = {"user_question": "调用知识助手", "trace_id": "t1", "best": None}
    consider_turn_artifact_candidate(
        turn,
        tool_name="sub_agent_call",
        tool_args={"agent_name": "knowledge-agent"},
        tool_output="这是子代理返回的可交付方案正文。" * 20,
        source_type="system",
        permission_scope="read",
    )

    assert turn["best"]["origin_type"] == "sub_agent"
    assert turn["best"]["result_type"] in {"knowledge", "generic"}


def test_sub_agent_batch_result_is_also_a_reusable_candidate():
    turn = {"user_question": "并行调用专家", "trace_id": "t2", "best": None}
    consider_turn_artifact_candidate(
        turn,
        tool_name="sub_agent_batch_call",
        tool_args={"agent_names": ["knowledge-agent", "data-agent"]},
        tool_output="并行专家返回的综合交付结果。" * 20,
        source_type="system",
        permission_scope="ask",
    )

    assert turn["best"]["origin_type"] == "sub_agent"


def test_should_inject_on_pure_followup_not_on_fresh_data_request():
    artifact = build_artifact_payload(
        tool_name="mcp_x",
        tool_args={},
        tool_output="z" * 300,
        source_type="mcp",
        user_question="上一轮",
        trace_id="1",
    )
    assert should_inject_session_artifact("把刚才的结果画成柱状图", artifact) is True
    assert should_inject_session_artifact("请重新查询最新数据", artifact) is False
    assert should_inject_session_artifact("继续分析上一轮的最新结果", artifact) is False


def test_should_inject_returns_false_when_artifact_is_none():
    assert should_inject_session_artifact("把刚才的结果画成柱状图", None) is False
    assert append_session_tool_artifact_to_system_prompt("base", "总结一下", None) == "base"


def test_should_not_inject_expired_or_failed_artifact():
    expired = build_artifact_payload(
        tool_name="api_tool",
        tool_args={},
        tool_output="过期结果 " * 30,
        source_type="generic_api",
        user_question="原始问题",
        trace_id="expired",
    )
    expired["expires_at"] = (
        datetime.now(timezone.utc) - timedelta(minutes=1)
    ).isoformat()

    failed = dict(expired)
    failed["expires_at"] = (
        datetime.now(timezone.utc) + timedelta(minutes=1)
    ).isoformat()
    failed["status"] = "failed"

    assert should_inject_session_artifact("总结一下刚才的结果", expired) is False
    assert should_inject_session_artifact("总结一下刚才的结果", failed) is False


def test_append_session_artifact_injects_block():
    artifact = build_artifact_payload(
        tool_name="api_tool",
        tool_args={"q": "test"},
        tool_output="result " * 50,
        source_type="generic_api",
        user_question="原始问题",
        trace_id="1",
    )
    out = append_session_tool_artifact_to_system_prompt(
        "系统提示",
        "总结一下上面的结果",
        artifact,
    )
    assert out.startswith(SESSION_ARTIFACT_BLOCK_MARKER)
    assert "api_tool" in out
    assert "系统提示" in out


def test_append_skips_greeting_without_context_ref():
    artifact = build_artifact_payload(
        tool_name="api_tool",
        tool_args={},
        tool_output="a" * 200,
        source_type="generic_api",
        user_question="q",
        trace_id="1",
    )
    assert append_session_tool_artifact_to_system_prompt("base", "你好", artifact) == "base"


def test_build_session_artifact_prompt_block_contains_rules():
    block = build_session_artifact_prompt_block(
        {
            "tool_name": "demo",
            "saved_at": "2026-01-01",
            "text_excerpt": "data",
        }
    )
    assert "不要对同一工具重复" in block


def test_filter_tools_for_reusable_result_keeps_transform_tools_only():
    class Tool:
        def __init__(self, name):
            self.name = name

    tools = [
        Tool("sub_agent_call"),
        Tool("execute_sql_query"),
        Tool("browser_read_visible"),
        Tool("write_file"),
    ]
    artifact = build_artifact_payload(
        tool_name="sub_agent_call",
        tool_args={},
        tool_output="可复用的结果正文 " * 30,
        source_type="system",
        user_question="原始问题",
        trace_id="trace-1",
    )

    filtered = filter_tools_for_reusable_result(
        tools,
        user_question="生成可视化分析报告\n\n---\n\n【被点击的 AI 回复】\n原回复",
        artifact=artifact,
    )

    assert [tool.name for tool in filtered] == ["write_file"]


def test_clicked_reply_refresh_action_does_not_inject_old_snapshot():
    artifact = build_artifact_payload(
        tool_name="api_tool",
        tool_args={},
        tool_output="上一轮结果 " * 30,
        source_type="generic_api",
        user_question="原始问题",
        trace_id="trace-refresh",
    )

    assert should_inject_session_artifact(
        "重新查询最新数据\n\n---\n\n【被点击的 AI 回复】\n这是最新数据",
        artifact,
    ) is False


@pytest.mark.asyncio
async def test_persist_without_candidate_invalidates_previous_snapshot():
    from app.services.ai.session_tool_artifact import persist_turn_artifact_candidate

    redis = AsyncMock()
    with patch("app.core.redis.get_redis", new_callable=AsyncMock, return_value=redis):
        await persist_turn_artifact_candidate(
            user_id="7",
            conversation_id="conv-1",
            turn_state={"best": None},
        )

    redis.delete.assert_awaited_once_with("conversation:7:conv-1:session_tool_artifact_v1")


@pytest.mark.asyncio
async def test_persist_on_interrupt_keeps_previous_snapshot_when_empty():
    from app.services.ai.session_tool_artifact import persist_turn_artifact_candidate

    redis = AsyncMock()
    with patch("app.core.redis.get_redis", new_callable=AsyncMock, return_value=redis):
        await persist_turn_artifact_candidate(
            user_id="7",
            conversation_id="conv-1",
            turn_state={"best": None},
            clear_if_empty=False,
        )

    redis.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_persist_candidate_writes_unified_result_and_legacy_compatibility(monkeypatch):
    from app.services.ai.session_tool_artifact import persist_turn_artifact_candidate

    unified = AsyncMock()
    legacy = AsyncMock()
    stack = AsyncMock()
    monkeypatch.setattr("app.services.ai.memory_service.memory_service.set_reusable_result", unified)
    monkeypatch.setattr("app.services.ai.memory_service.memory_service.push_reusable_result", stack)
    monkeypatch.setattr("app.services.ai.memory_service.memory_service.set_session_tool_artifact", legacy)

    result_summary = await persist_turn_artifact_candidate(
        user_id="7",
        conversation_id="conv-1",
        turn_state={
            "user_question": "调用知识助手",
            "trace_id": "trace-1",
            "best": {
                "result_id": "result-1",
                "result_type": "knowledge",
                "origin_type": "sub_agent",
                "origin_name": "sub_agent_call",
                "status": "completed",
                "content": "知识助手返回的方案正文",
                "structured": None,
            },
        },
    )

    unified.assert_not_awaited()
    stack.assert_awaited_once()
    legacy.assert_awaited_once()
    assert result_summary["result_id"] == "result-1"
    assert result_summary["origin_name"] == "sub_agent_call"
    assert "tool_args" not in result_summary


@pytest.mark.asyncio
async def test_persist_candidate_does_not_report_saved_when_unified_write_fails(monkeypatch):
    from app.services.ai.session_tool_artifact import persist_turn_artifact_candidate

    stack = AsyncMock(return_value=False)
    legacy = AsyncMock()
    monkeypatch.setattr("app.services.ai.memory_service.memory_service.push_reusable_result", stack)
    monkeypatch.setattr("app.services.ai.memory_service.memory_service.set_session_tool_artifact", legacy)

    result = await persist_turn_artifact_candidate(
        user_id="7",
        conversation_id="conv-1",
        turn_state={
            "best": {
                "result_id": "result-1",
                "result_type": "generic",
                "status": "completed",
                "content": "这是一个有效的结果正文，足够用于复用分析。",
            }
        },
    )

    assert result is None
    legacy.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_candidate_does_not_replace_existing_unified_result(monkeypatch):
    from app.services.ai.session_tool_artifact import persist_turn_artifact_candidate

    unified = AsyncMock()
    stack = AsyncMock()
    legacy = AsyncMock()
    monkeypatch.setattr("app.services.ai.memory_service.memory_service.set_reusable_result", unified)
    monkeypatch.setattr("app.services.ai.memory_service.memory_service.push_reusable_result", stack)
    monkeypatch.setattr("app.services.ai.memory_service.memory_service.set_session_tool_artifact", legacy)

    await persist_turn_artifact_candidate(
        user_id="7",
        conversation_id="conv-1",
        turn_state={
            "best": {
                "result_id": "failed-1",
                "status": "failed",
                "content": "工具失败",
            }
        },
    )

    unified.assert_not_awaited()
    stack.assert_not_awaited()
    legacy.assert_not_awaited()
