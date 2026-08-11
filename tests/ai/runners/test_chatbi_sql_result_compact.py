"""Tests for ChatBI large SQL compact + deferred incomplete reply rescue."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.services.ai.config import ChatConfig
from app.services.ai.runners.chatbi.sql_result_compact import (
    compact_sql_result_for_model,
    looks_like_deferred_continue_query_reply,
    looks_like_deferred_data_reply,
    mark_deferred_continue_query,
    should_force_deferred_continue_query,
    should_rescue_deferred_sql_reply,
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
    rows = [[f"A{i}", f"RACK-{i % 5}", "server"] for i in range(110)]
    payload = {
        "columns": [{"name": "asset_id"}, {"name": "rack"}, {"name": "type"}],
        "items": rows,
    }
    compact_raw = compact_sql_result_for_model(_FakeRunner(), json.dumps(payload, ensure_ascii=False))
    assert compact_raw is not None
    compact = json.loads(compact_raw)
    assert compact["total_row_count"] == 110
    assert compact["sample_row_count"] == 15
    assert len(compact["items"]) == 15
    assert "_model_context_note" in compact
    assert "禁止承诺" in compact["_model_context_note"]
    assert "dimension_summaries" in compact


def test_compact_sql_result_for_model_skips_small_payload():
    payload = {"columns": [{"name": "id"}], "items": [[1], [2], [3]]}
    assert compact_sql_result_for_model(_FakeRunner(), json.dumps(payload)) is None


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

    rows = [[f"id-{i}", f"type-{i % 3}"] for i in range(50)]
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
        sql="SELECT id, type FROM demo LIMIT 100",
        data_source="mysql_aiagent",
        dataset_name="demo",
    )
    compact = json.loads(returned)
    assert compact["total_row_count"] == 50
    assert len(compact["items"]) == 15
    assert state.pending_sql_tool_full_output == full
    assert state.last_successful_sql_output == full
    cached = state.successful_sqls[
        runner._normalize_sql_text("SELECT id, type FROM demo LIMIT 100")
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
    assert "查看数据依据" in text
