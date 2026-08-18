"""Tests for ChatBI large SQL compact + deferred incomplete reply rescue."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.services.ai.config import ChatConfig
from app.services.ai.runners.chatbi.sql_result_compact import (
    compact_sql_result_for_model,
    looks_like_contradictory_empty_reply,
    looks_like_deferred_continue_query_reply,
    looks_like_deferred_data_reply,
    looks_like_process_only_reply,
    mark_deferred_continue_query,
    mark_successful_nonempty_sql,
    mark_visible_content_emitted,
    should_force_deferred_continue_query,
    should_rescue_contradictory_empty_reply,
    should_rescue_deferred_sql_reply,
    should_rescue_process_only_after_sql,
    should_rescue_sql_without_followup_content,
)
from app.services.ai.runtime.agentscope.tools import RuntimeToolSpec


@pytest.fixture
def data_config():
    return ChatConfig(
        agent_id="data-agent-id",
        agent_name="DataAgent",
        agent_version=None,
        model_name="gpt-4o",
        temperature=0.0,
        system_prompt="You are a data agent.",
        tools=["update_dashboard_context"],
    )


class _FakeRunner:
    @staticmethod
    def _try_parse_json_output(output):
        if isinstance(output, (dict, list)):
            return output
        return json.loads(output)


def test_looks_like_deferred_data_reply_matches_screenshot_style():
    text = (
        "查询成功，已获取上海 WGQ 园区 M601 机房的资产清单。"
        "结果较多，我读取完整数据后为您汇总。"
    )
    assert looks_like_deferred_data_reply(text) is True
    assert looks_like_deferred_continue_query_reply(text) is False


def test_looks_like_deferred_continue_query_matches_rack_refinement():
    text = (
        "查询成功。不过当前结果仅返回了机柜的字母分组汇总 (A/B/C/D/E)，"
        "而非各机柜的独立编码明细。让我进一步按完整机柜编码统计，"
        "以呈现每个具体机柜的 U 位占用情况。"
    )
    assert looks_like_deferred_continue_query_reply(text) is True
    assert looks_like_deferred_data_reply(text) is False


def test_looks_like_deferred_data_reply_ignores_substantive_answers():
    text = (
        "查询成功，共 110 行。\n\n"
        "> 业务目标：机房资产清单\n\n"
        "## 汇总\n"
        "- 总数：110\n"
        "- 按类型：服务器 80，网络 30\n\n"
        "| 资产编号 | 机柜 |\n"
        "| --- | --- |\n"
        "| A1 | C17 |\n"
    )
    assert looks_like_deferred_data_reply(text) is False
    assert looks_like_deferred_continue_query_reply(text) is False


def test_compact_sql_result_for_model_samples_large_payload():
    rows = [[f"A{i}", f"RACK-{i % 5}", "server"] for i in range(600)]
    payload = {
        "columns": [{"name": "asset_id"}, {"name": "rack"}, {"name": "type"}],
        "items": rows,
    }
    compact_raw = compact_sql_result_for_model(_FakeRunner(), json.dumps(payload, ensure_ascii=False))
    assert compact_raw is not None
    compact = json.loads(compact_raw)
    assert compact["total_row_count"] == 600
    assert compact["sample_row_count"] == 500
    assert len(compact["items"]) == 500
    assert "_model_context_note" in compact
    assert "必须告知用户" in compact["_model_context_note"]
    assert "并非对全部明细的逐行全量分析" in compact["_model_context_note"]
    assert "dimension_summaries" in compact


def test_compact_sql_result_uses_exact_total_instead_of_returned_rows():
    rows = [[i, f"RACK-{i % 5}"] for i in range(1000)]
    payload = {
        "columns": [{"name": "id"}, {"name": "rack"}],
        "items": rows,
        "total_count": 5000,
        "returned_count": 1000,
        "truncated": True,
        "count_status": "exact",
    }

    compact = json.loads(
        compact_sql_result_for_model(_FakeRunner(), json.dumps(payload, ensure_ascii=False))
    )

    assert compact["total_row_count"] == 5000
    assert compact["returned_row_count"] == 1000
    assert compact["truncated"] is True
    assert compact["count_status"] == "exact"
    assert "全部 5000 行中的前 500 行样例" in compact["_model_context_note"]


def test_compact_sql_result_does_not_infer_unknown_total_from_sample_size():
    rows = [[i] for i in range(1000)]
    payload = {
        "columns": [{"name": "id"}],
        "items": rows,
        "total_count": None,
        "returned_count": 1000,
        "truncated": None,
        "count_status": "unknown",
    }

    compact = json.loads(
        compact_sql_result_for_model(_FakeRunner(), json.dumps(payload, ensure_ascii=False))
    )

    assert compact["total_row_count"] is None
    assert compact["returned_row_count"] == 1000
    assert "总数未统计" in compact["_model_context_note"]


def test_build_model_result_scope_marks_sample_mode():
    from app.services.ai.runners.chatbi.sql_result_compact import build_model_result_scope

    rows = [[i] for i in range(600)]
    payload = json.dumps({"columns": [{"name": "id"}], "items": rows})
    scope = build_model_result_scope(_FakeRunner(), payload)
    assert scope["mode"] == "sample"
    assert scope["total_row_count"] == 600
    assert scope["model_row_count"] == 500
    assert "并非逐行全量分析" in scope["user_notice"]


def test_build_model_result_scope_preserves_unknown_total():
    from app.services.ai.runners.chatbi.sql_result_compact import build_model_result_scope

    rows = [[i] for i in range(1000)]
    payload = json.dumps(
        {
            "columns": [{"name": "id"}],
            "items": rows,
            "total_count": None,
            "returned_count": 1000,
            "truncated": None,
            "count_status": "unknown",
        }
    )

    scope = build_model_result_scope(_FakeRunner(), payload)

    assert scope["mode"] == "sample"
    assert scope["total_row_count"] is None
    assert scope["model_row_count"] == 500
    assert "总数未统计" in scope["user_notice"]


def test_compact_sql_result_for_model_skips_under_threshold():
    payload = {
        "columns": [{"name": "id"}],
        "items": [[i] for i in range(500)],
    }
    assert compact_sql_result_for_model(_FakeRunner(), json.dumps(payload)) is None


def test_should_rescue_sql_without_followup_after_process_narration():
    """截图回归：过程句在前 → SQL 成功 → 无后续正文 → 必须缓存合成。"""
    state = SimpleNamespace(
        empty_sql_result=False,
        diagnostic_sql_pending_final=False,
        has_successful_nonempty_sql=True,
        last_successful_sql_output='{"items":[["dev-1","normal"]]}',
        sql_repeat_gate_block=False,
        deferred_continue_query=False,
        full_content="现在查询该机房的设备实例，统计各状态数量。",
        last_visible_content_at=1,
        last_successful_nonempty_sql_at=2,
        event_seq=2,
    )
    assert should_rescue_sql_without_followup_content(state) is True
    assert should_force_deferred_continue_query(state) is False


def test_should_rescue_sql_without_followup_for_distribution_narration():
    state = SimpleNamespace(
        empty_sql_result=False,
        diagnostic_sql_pending_final=False,
        has_successful_nonempty_sql=True,
        last_successful_sql_output='{"items":[["normal",10]]}',
        sql_repeat_gate_block=False,
        deferred_continue_query=False,
        full_content="下面统计设备状态分布。",
        last_visible_content_at=3,
        last_successful_nonempty_sql_at=4,
        event_seq=4,
    )
    assert should_rescue_sql_without_followup_content(state) is True


def test_should_rescue_latest_sql_b_after_intermediate_a_promise():
    """已查到 A，继续查 B 且 B 成功后无正文 → 基于 B 合成。"""
    state = SimpleNamespace(
        empty_sql_result=False,
        diagnostic_sql_pending_final=False,
        has_successful_nonempty_sql=True,
        last_successful_sql_output='{"items":[["B",1]]}',
        sql_repeat_gate_block=False,
        deferred_continue_query=False,
        full_content="已查到机房清单，现在继续查询设备实例。",
        last_visible_content_at=5,
        last_successful_nonempty_sql_at=8,
        event_seq=8,
    )
    assert should_rescue_sql_without_followup_content(state) is True


def test_substantive_answer_after_sql_is_not_rescued_by_timing():
    state = SimpleNamespace(
        empty_sql_result=False,
        diagnostic_sql_pending_final=False,
        has_successful_nonempty_sql=True,
        last_successful_sql_output='{"items":[[110]]}',
        sql_repeat_gate_block=False,
        deferred_continue_query=False,
        ready_to_answer=True,
        full_content=(
            "查询成功，共 110 台设备。\n\n"
            "## 汇总\n"
            "- 正常：37\n"
            "- 离线：15\n\n"
            "| 指标 | 值 |\n"
            "| --- | --- |\n"
            "| device_count | 110 |\n"
        ),
        last_visible_content_at=9,
        last_successful_nonempty_sql_at=7,
        event_seq=9,
    )
    assert should_rescue_sql_without_followup_content(state) is False
    assert should_rescue_process_only_after_sql(state) is False
    assert should_rescue_deferred_sql_reply(state) is False
    assert should_force_deferred_continue_query(state) is False


def test_process_only_after_sql_auxiliary_rescue():
    state = SimpleNamespace(
        empty_sql_result=False,
        diagnostic_sql_pending_final=False,
        has_successful_nonempty_sql=True,
        last_successful_sql_output='{"items":[[1]]}',
        sql_repeat_gate_block=False,
        deferred_continue_query=False,
        full_content="现在查询该机房的设备实例。",
        last_visible_content_at=4,
        last_successful_nonempty_sql_at=3,
        event_seq=4,
    )
    assert looks_like_process_only_reply(state.full_content) is True
    assert should_rescue_sql_without_followup_content(state) is False
    assert should_rescue_process_only_after_sql(state) is True


def test_mark_helpers_order_sql_after_content():
    state = SimpleNamespace(
        event_seq=0,
        last_visible_content_at=0,
        last_successful_nonempty_sql_at=0,
        last_tool_name="",
    )
    mark_visible_content_emitted(state)
    assert state.last_visible_content_at == 1
    mark_successful_nonempty_sql(state)
    assert state.last_successful_nonempty_sql_at == 2
    assert state.last_successful_nonempty_sql_at > state.last_visible_content_at


def test_looks_like_contradictory_empty_reply_matches_screenshot():
    text = (
        "查询返回为空。我需要确认上海 WGQ 园区在数据中的实际城市编码和名称。"
        "让我先查看园区基础信息表中的数据分布。"
    )
    assert looks_like_contradictory_empty_reply(text) is True
    assert looks_like_deferred_continue_query_reply(text) is True


def test_should_rescue_contradictory_empty_when_cache_has_rows():
    text = (
        "查询返回为空。我需要确认上海 WGQ 园区在数据中的实际城市编码和名称。"
        "让我先查看园区基础信息表中的数据分布。"
    )
    state = SimpleNamespace(
        ready_to_answer=True,
        empty_sql_result=False,
        has_successful_nonempty_sql=True,
        last_successful_sql_output='{"items":[[110,37,0,15,78,32,310]]}',
        sql_repeat_gate_block=False,
        deferred_continue_query=False,
        full_content=text,
    )
    assert should_rescue_contradictory_empty_reply(state) is True
    assert should_force_deferred_continue_query(state) is False
    assert should_rescue_deferred_sql_reply(state) is False

    state.empty_sql_result = True
    state.has_successful_nonempty_sql = False
    assert should_rescue_contradictory_empty_reply(state) is False


def test_should_rescue_deferred_sql_reply_requires_ready_cache():
    deferred = "查询成功，结果较多，我读取完整数据后为您汇总。"
    state = SimpleNamespace(
        ready_to_answer=True,
        last_successful_sql_output='{"items":[[1]]}',
        sql_repeat_gate_block=False,
        deferred_continue_query=False,
        full_content=deferred,
    )
    assert should_rescue_deferred_sql_reply(state) is True

    state.ready_to_answer = False
    assert should_rescue_deferred_sql_reply(state) is False


def test_should_force_deferred_continue_query_for_refinement_promise():
    text = (
        "查询成功。不过当前结果仅返回了机柜的字母分组汇总 (A/B/C/D/E)，"
        "而非各机柜的独立编码明细。让我进一步按完整机柜编码统计，"
        "以呈现每个具体机柜的 U 位占用情况。"
    )
    state = SimpleNamespace(
        ready_to_answer=True,
        last_successful_sql_output='{"items":[[1],[2],[3],[4],[5]]}',
        sql_repeat_gate_block=False,
        deferred_continue_query=False,
        full_content=text,
    )
    assert should_force_deferred_continue_query(state) is True
    assert should_rescue_deferred_sql_reply(state) is False

    mark_deferred_continue_query(state)
    assert state.deferred_continue_query is True
    assert should_force_deferred_continue_query(state) is True


def test_deferred_continue_query_repair_policy(data_config):
    from app.services.ai.runners.chatbi.repair_policy import (
        build_repair_message,
        build_repair_title,
        current_repair_kind,
        resolve_repair_tool_choice,
    )
    from app.services.ai.runners.data_agent_runner import DataAgentRunner, _DataRunState

    runner = DataAgentRunner(config=data_config, trace_id="trace-deferred-continue", trace_buffer=[])
    state = _DataRunState(
        requires_fresh_data=True,
        schema_completed=True,
        sql_completed=True,
        deferred_continue_query=True,
        last_successful_sql_output='{"items":[[1]]}',
    )
    assert current_repair_kind(state) == "deferred_continue_query"
    assert "继续细化查数" in build_repair_message(state)
    assert build_repair_title(state) == "继续细化查数"
    choice = resolve_repair_tool_choice(state)
    assert choice is not None
    assert getattr(choice, "mode", None) == "execute_sql_query"

    runner._reset_state_for_repair(state)
    assert state.deferred_continue_query is False
    assert state.sql_completed is False
    assert state.last_successful_sql_output == '{"items":[[1]]}'


@pytest.mark.asyncio
async def test_sql_gate_returns_compacted_payload_but_keeps_full_cache(data_config):
    from app.services.ai.runners.data_agent_runner import DataAgentRunner, _DataRunState

    rows = [[f"id-{i}", f"type-{i % 3}"] for i in range(600)]
    full = json.dumps(
        {
            "columns": [{"name": "id"}, {"name": "type"}],
            "items": rows,
        },
        ensure_ascii=False,
    )

    async def _fake_sql(**kwargs):
        return full

    runner = DataAgentRunner(config=data_config, trace_id="trace-compact", trace_buffer=[])
    state = _DataRunState(requires_fresh_data=True, schema_completed=True)
    spec = RuntimeToolSpec(
        name="execute_sql_query",
        description="sql",
        parameters_schema={},
        source_type="static",
        callable=_fake_sql,
        permission_scope="read",
    )
    wrapped = runner._wrap_tools_with_schema_gate([spec], state)[0]
    returned = await wrapped.callable(
        sql="SELECT id, type FROM demo LIMIT 700",
        data_source="mysql_aiagent",
        dataset_name="demo",
    )
    compact = json.loads(returned)
    assert compact["total_row_count"] == 600
    assert len(compact["items"]) == 500
    assert state.pending_sql_tool_full_output == full
    assert state.last_successful_sql_output == full
    cached = state.successful_sqls[
        runner._normalize_sql_text("SELECT id, type FROM demo LIMIT 700")
    ]
    assert cached == full


def test_apply_sql_repeat_gate_prefers_full_successful_cache(data_config):
    from app.services.ai.runners.data_agent_runner import DataAgentRunner, _DataRunState

    runner = DataAgentRunner(config=data_config, trace_id="trace-repeat-full", trace_buffer=[])
    full = json.dumps({"columns": [{"name": "id"}], "items": [[i] for i in range(40)]})
    sql = "SELECT id FROM demo LIMIT 100"
    state = _DataRunState(
        requires_fresh_data=True,
        schema_completed=True,
        successful_sqls={runner._normalize_sql_text(sql): full},
    )
    gate_output = (
        "[SQL_REPEAT_GATE] duplicated\n\n"
        '{"columns":[{"name":"id"}],"items":[[0]],"total_row_count":40,"sample_row_count":1}'
    )
    parsed, should_save = runner._apply_sql_tool_result(
        state,
        tool_args={"sql": sql},
        output=gate_output,
    )
    assert should_save is False
    assert state.sql_repeat_gate_block is True
    assert state.last_successful_sql_output == full
    assert isinstance(parsed, dict)
    assert len(parsed["items"]) == 40


def test_global_guardrails_forbid_deferred_and_bash_dump():
    from app.services.ai.executors.prompts import DataQueryPrompts

    text = DataQueryPrompts.GLOBAL_GUARDRAILS
    assert "读取完整数据后再汇总" in text
    assert "让我进一步按" in text
    assert "Bash/Read/Grep" in text
    assert "查询结果明细" in text
    assert "样例而非逐行全量分析" in text
    assert "count_status=exact" in text
    assert "数据库总数未统计" in text
