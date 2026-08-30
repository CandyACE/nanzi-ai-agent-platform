import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.ai.chatbi_result_stack import (
    ChatBIAnalysisContext,
    ChatBIResultRef,
    push_result_ref,
    resolve_result_reference,
)
from app.services.ai.memory_service import MemoryService


@pytest.fixture(scope="function", autouse=True)
async def init_infrastructure():
    with patch("app.core.database.init_db", new_callable=AsyncMock), \
         patch("app.core.database.close_db", new_callable=AsyncMock), \
         patch("app.core.redis.init_redis", new_callable=AsyncMock), \
         patch("app.core.redis.close_redis", new_callable=AsyncMock), \
         patch("app.core.orm.AsyncSessionLocal", new_callable=MagicMock):
        yield


def _ref(result_id: str, question: str, parent: str | None = None) -> ChatBIResultRef:
    return ChatBIResultRef(
        result_id=result_id,
        parent_result_id=parent,
        question=question,
        dataset_name="sales",
        sql="SELECT 1",
        rows={"rows": [{"value": 1}]},
        analysis_context=ChatBIAnalysisContext(metrics=["销售额"]),
    )


def test_push_result_ref_keeps_ten_newest_and_current():
    stack = []
    for index in range(12):
        stack = push_result_ref(stack, _ref(f"r{index}", f"问题 {index}"))
    assert [item.result_id for item in stack] == [f"r{i}" for i in range(2, 12)]
    assert resolve_result_reference(stack, "当前结果").result.result_id == "r11"


def test_resolve_current_previous_and_explicit_result_reference():
    stack = [_ref("root", "整体销售额"), _ref("region", "按区域分析", "root")]
    assert resolve_result_reference(stack, "这个结果").result.result_id == "region"
    assert resolve_result_reference(stack, "上一个结果").result.result_id == "root"
    assert resolve_result_reference(stack, "result:root").result.result_id == "root"


def test_resolve_bare_result_id_as_explicit_reference():
    stack = [_ref("result_root123", "整体销售额"), _ref("result_region456", "按区域分析")]
    assert resolve_result_reference(stack, "result_root123").result.result_id == "result_root123"


def test_result_ref_from_legacy_payload_ignores_unknown_fields_and_maps_saved_time():
    ref = ChatBIResultRef.from_dict({
        "question": "历史查询",
        "sql": "SELECT 1",
        "saved_at": "2026-07-19T10:00:00",
        "legacy_only": "ignored",
        "filters": [{"field": "region", "value": "华东"}],
    })
    assert ref.question == "历史查询"
    assert ref.created_at == "2026-07-19T10:00:00"
    assert ref.sql == "SELECT 1"


def test_descriptive_reference_returns_ambiguity_instead_of_guessing():
    stack = [_ref("r1", "按区域看销售额"), _ref("r2", "按区域看订单量")]
    resolved = resolve_result_reference(stack, "区域那张表")
    assert resolved.result is None
    assert [item.result_id for item in resolved.candidates] == ["r2", "r1"]


def test_descriptive_reference_can_select_unique_result():
    stack = [_ref("root", "整体销售额"), _ref("region", "按区域分析", "root")]
    resolved = resolve_result_reference(stack, "区域那张表")
    assert resolved.result.result_id == "region"


class _FakeRedis:
    def __init__(self):
        self.values = {}
        self.expires = {}
        self.eval_calls = []

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value, ex=None):
        self.values[key] = value
        self.expires[key] = ex

    async def eval(self, script, numkeys, *args):
        self.eval_calls.append((script, numkeys, args))
        import json

        if numkeys == 1:
            key, payload_json, ttl, max_depth, result_id = args
            raw = self.values.get(key)
            try:
                existing = json.loads(raw) if raw else []
            except (TypeError, ValueError, json.JSONDecodeError):
                existing = []
            stack = [
                item
                for item in existing
                if isinstance(item, dict)
                and (not result_id or str(item.get("result_id") or "") != result_id)
            ]
            stack.append(json.loads(payload_json))
            stack = stack[-max(1, int(max_depth)) :]
            self.values[key] = json.dumps(stack, ensure_ascii=False)
            self.expires[key] = int(ttl)
            return 1

        current_key, stack_key, payload_json, ttl, max_depth, result_id = args
        raw = self.values.get(stack_key)
        try:
            existing = json.loads(raw) if raw else []
        except (TypeError, ValueError, json.JSONDecodeError):
            existing = []
        stack = [
            item
            for item in existing
            if isinstance(item, dict)
            and (not result_id or str(item.get("result_id") or "") != result_id)
        ]
        stack.append(json.loads(payload_json))
        stack = stack[-max(1, int(max_depth)) :]
        self.values[current_key] = payload_json
        self.values[stack_key] = json.dumps(stack, ensure_ascii=False)
        self.expires[current_key] = int(ttl)
        self.expires[stack_key] = int(ttl)
        return 1

    async def delete(self, key):
        self.values.pop(key, None)


@pytest.mark.asyncio
async def test_memory_service_result_stack_is_isolated_and_prefers_current(monkeypatch):
    redis = _FakeRedis()
    monkeypatch.setattr("app.services.ai.memory_service.get_redis", AsyncMock(return_value=redis))
    service = MemoryService()
    await service.push_data_result_ref("u1", "c1", _ref("root", "整体销售额").to_dict())
    await service.push_data_result_ref("u1", "c1", _ref("region", "按区域分析", "root").to_dict())
    await service.push_data_result_ref("u2", "c1", _ref("other", "其他用户结果").to_dict())

    stack = await service.get_data_result_stack("u1", "c1")
    current = await service.get_current_data_result("u1", "c1")
    assert [item["result_id"] for item in stack] == ["root", "region"]
    assert current["result_id"] == "region"
    assert current["rows"] == {"rows": [{"value": 1}]}
    assert any(numkeys == 1 for _, numkeys, _ in redis.eval_calls)


@pytest.mark.asyncio
async def test_reusable_result_current_and_stack_use_user_conversation_scope(monkeypatch):
    redis = _FakeRedis()
    monkeypatch.setattr("app.services.ai.memory_service.get_redis", AsyncMock(return_value=redis))
    service = MemoryService()
    first = {"result_id": "r1", "result_type": "generic", "status": "completed"}
    second = {"result_id": "r2", "result_type": "file", "status": "completed"}

    await service.set_reusable_result("u1", "c1", first)
    await service.push_reusable_result("u1", "c1", second)

    assert (await service.get_reusable_result("u1", "c1"))["result_id"] == "r2"
    assert [item["result_id"] for item in await service.get_reusable_result_stack("u1", "c1")] == [
        "r1",
        "r2",
    ]
    assert "conversation:u1:c1:reusable_result_v1:current" in redis.values
    assert "conversation:u1:c1:reusable_result_v1:stack" in redis.values
    assert redis.expires["conversation:u1:c1:reusable_result_v1:current"] == service.ttl
    assert redis.expires["conversation:u1:c1:reusable_result_v1:stack"] == service.ttl
    assert len(redis.eval_calls) == 2


@pytest.mark.asyncio
async def test_reusable_result_push_updates_current_and_stack_in_one_redis_script(monkeypatch):
    redis = _FakeRedis()
    monkeypatch.setattr("app.services.ai.memory_service.get_redis", AsyncMock(return_value=redis))
    service = MemoryService()

    written = await service.push_reusable_result(
        "u1",
        "c1",
        {"result_id": "atomic-1", "result_type": "generic", "status": "completed", "content": "结果"},
    )

    assert written is True
    assert len(redis.eval_calls) == 1
    _, numkeys, args = redis.eval_calls[0]
    assert numkeys == 2
    assert args[0].endswith(":reusable_result_v1:current")
    assert args[1].endswith(":reusable_result_v1:stack")


@pytest.mark.asyncio
async def test_reusable_result_push_is_idempotent_and_cleanup_removes_both_keys(monkeypatch):
    redis = _FakeRedis()
    monkeypatch.setattr("app.services.ai.memory_service.get_redis", AsyncMock(return_value=redis))
    service = MemoryService()
    result = {"result_id": "same", "result_type": "generic", "status": "completed"}

    await service.push_reusable_result("u1", "c1", result)
    await service.push_reusable_result("u1", "c1", result)
    await service.clear_history("u1", "c1")

    assert "conversation:u1:c1:reusable_result_v1:current" not in redis.values
    assert "conversation:u1:c1:reusable_result_v1:stack" not in redis.values


@pytest.mark.asyncio
async def test_reusable_result_stack_keeps_ten_newest_entries(monkeypatch):
    redis = _FakeRedis()
    monkeypatch.setattr("app.services.ai.memory_service.get_redis", AsyncMock(return_value=redis))
    service = MemoryService()

    for index in range(12):
        await service.push_reusable_result(
            "u1",
            "c1",
            {"result_id": f"r{index}", "result_type": "generic", "status": "completed"},
        )

    stack = await service.get_reusable_result_stack("u1", "c1")
    assert [item["result_id"] for item in stack] == [f"r{index}" for index in range(2, 12)]
    assert (await service.get_reusable_result("u1", "c1"))["result_id"] == "r11"


@pytest.mark.asyncio
async def test_followup_save_dual_writes_legacy_and_structured_result(monkeypatch):
    from app.services.ai.data_query_semantic_intent import DataQuerySemanticIntent
    from app.services.ai.runners.chatbi.followup_data import save_last_data_result_for_followups

    legacy = AsyncMock()
    unified = AsyncMock()
    unified_stack = AsyncMock()
    push = AsyncMock()
    monkeypatch.setattr("app.services.ai.memory_service.memory_service.set_last_data_result", legacy)
    monkeypatch.setattr("app.services.ai.memory_service.memory_service.set_reusable_result", unified)
    monkeypatch.setattr("app.services.ai.memory_service.memory_service.push_reusable_result", unified_stack)
    monkeypatch.setattr(
        "app.services.ai.memory_service.memory_service.get_data_result_stack",
        AsyncMock(return_value=[{"result_id": "parent"}]),
    )
    monkeypatch.setattr("app.services.ai.memory_service.memory_service.push_data_result_ref", push)
    runner = SimpleNamespace(
        conversation_id="conv-1",
        trace_id="trace-1",
        _current_user_id=lambda: 7,
        _standalone_query="查询本月各区域销售额",
        _semantic_intent=DataQuerySemanticIntent(
            metrics=["销售额"],
            dimensions=["区域"],
            time_range="本月",
            grain="day",
        ),
        _last_run_state=SimpleNamespace(followup_data_saved=False),
    )
    result_summary = await save_last_data_result_for_followups(
        runner,
        {"sql": "SELECT region, SUM(amount) FROM sales", "dataset_name": "sales"},
        {"rows": [{"region": "华东", "amount": 10}]},
    )

    legacy.assert_awaited_once()
    unified.assert_not_awaited()
    unified_stack.assert_awaited_once()
    unified_payload = unified_stack.await_args.args[2]
    assert unified_payload["result_type"] == "data"
    assert unified_payload["rows"] == {"rows": [{"region": "华东", "amount": 10}]}
    assert unified_payload["saved_at"].endswith("+00:00")
    assert unified_payload["status"] == "completed"
    payload = push.await_args.args[2]
    assert payload["parent_result_id"] == "parent"
    assert payload["analysis_context"]["metrics"] == ["销售额"]
    assert payload["analysis_context"]["dimensions"] == ["区域"]
    assert payload["freshness"] == "dynamic"
    assert payload["source_ref"] == "dataset://sales"
    assert payload["observed_at"]
    assert payload["result_status"] == "success_non_empty"
    assert runner._last_run_state.followup_data_saved is True
    assert result_summary["result_id"] == unified_payload["result_id"]
    assert result_summary["result_type"] == "data"


@pytest.mark.asyncio
async def test_followup_save_does_not_report_saved_when_unified_write_fails(monkeypatch):
    from app.services.ai.runners.chatbi.followup_data import save_last_data_result_for_followups

    legacy = AsyncMock()
    unified_stack = AsyncMock(return_value=False)
    monkeypatch.setattr("app.services.ai.memory_service.memory_service.set_last_data_result", legacy)
    monkeypatch.setattr(
        "app.services.ai.memory_service.memory_service.push_reusable_result",
        unified_stack,
    )
    monkeypatch.setattr(
        "app.services.ai.memory_service.memory_service.get_data_result_stack",
        AsyncMock(return_value=[]),
    )
    data_stack = AsyncMock()
    monkeypatch.setattr(
        "app.services.ai.memory_service.memory_service.push_data_result_ref",
        data_stack,
    )
    runner = SimpleNamespace(
        conversation_id="conv-1",
        trace_id="trace-fail",
        _current_user_id=lambda: 7,
        _standalone_query="查询销售额",
        _semantic_intent=None,
        _last_run_state=SimpleNamespace(followup_data_saved=False),
    )

    result = await save_last_data_result_for_followups(
        runner,
        {"sql": "SELECT amount FROM sales"},
        {"rows": [{"amount": 10}]},
    )

    assert result is None
    data_stack.assert_not_awaited()
    assert runner._last_run_state.followup_data_saved is False


@pytest.mark.asyncio
async def test_followup_save_skips_empty_result_for_reusable_cache(monkeypatch):
    from app.services.ai.runners.chatbi.followup_data import save_last_data_result_for_followups

    legacy = AsyncMock()
    unified = AsyncMock()
    unified_stack = AsyncMock()
    monkeypatch.setattr("app.services.ai.memory_service.memory_service.set_last_data_result", legacy)
    monkeypatch.setattr("app.services.ai.memory_service.memory_service.set_reusable_result", unified)
    monkeypatch.setattr("app.services.ai.memory_service.memory_service.push_reusable_result", unified_stack)
    runner = SimpleNamespace(
        conversation_id="conv-1",
        trace_id="trace-empty",
        _current_user_id=lambda: 7,
        _standalone_query="查询不存在的数据",
        _semantic_intent=None,
        _last_run_state=SimpleNamespace(followup_data_saved=False),
    )

    await save_last_data_result_for_followups(
        runner,
        {"sql": "SELECT * FROM demo"},
        {"rows": []},
    )

    legacy.assert_not_awaited()
    unified.assert_not_awaited()
    unified_stack.assert_not_awaited()


@pytest.mark.asyncio
async def test_chatbi_followup_loader_prefers_unified_data_result(monkeypatch):
    from app.services.ai.runners.chatbi.followup_data import load_last_data_result

    unified = {
        "result_id": "unified-1",
        "result_type": "data",
        "structured": {"rows": [{"value": 7}]},
    }
    monkeypatch.setattr(
        "app.services.ai.memory_service.memory_service.get_reusable_result",
        AsyncMock(return_value=unified),
    )
    legacy = AsyncMock(return_value={"rows": [{"value": 1}]})
    monkeypatch.setattr(
        "app.services.ai.memory_service.memory_service.get_current_data_result",
        legacy,
    )
    runner = SimpleNamespace(
        conversation_id="conv-1",
        _current_user_id=lambda: 7,
    )

    result = await load_last_data_result(runner)

    assert result["result_id"] == "unified-1"
    assert result["rows"] == {"rows": [{"value": 7}]}
    legacy.assert_not_awaited()


@pytest.mark.asyncio
async def test_chatbi_followup_loader_falls_back_to_unified_stack_when_current_is_empty(monkeypatch):
    from app.services.ai.runners.chatbi.followup_data import load_last_data_result

    monkeypatch.setattr(
        "app.services.ai.memory_service.memory_service.get_reusable_result",
        AsyncMock(
            return_value={
                "result_id": "empty-current",
                "result_type": "data",
                "result_status": "success_empty",
                "rows": {"rows": []},
            }
        ),
    )
    monkeypatch.setattr(
        "app.services.ai.memory_service.memory_service.get_reusable_result_stack",
        AsyncMock(
            return_value=[
                {
                    "result_id": "stacked-data",
                    "result_type": "data",
                    "rows": {"rows": [{"value": 9}]},
                    "structured": {"rows": [{"value": 9}]},
                }
            ]
        ),
    )
    legacy = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "app.services.ai.memory_service.memory_service.get_current_data_result",
        legacy,
    )
    runner = SimpleNamespace(
        conversation_id="conv-1",
        _current_user_id=lambda: 7,
    )

    result = await load_last_data_result(runner)

    assert result["result_id"] == "stacked-data"
    assert result["rows"] == {"rows": [{"value": 9}]}
    legacy.assert_not_awaited()


@pytest.mark.asyncio
async def test_chatbi_followup_loader_prefers_selected_stack_item(monkeypatch):
    from app.services.ai.runners.chatbi.followup_data import load_last_data_result

    monkeypatch.setattr(
        "app.services.ai.memory_service.memory_service.get_reusable_result",
        AsyncMock(
            return_value={
                "result_id": "current-data",
                "result_type": "data",
                "structured": {"rows": [{"value": 1}]},
            }
        ),
    )
    monkeypatch.setattr(
        "app.services.ai.memory_service.memory_service.get_reusable_result_stack",
        AsyncMock(
            return_value=[
                {
                    "result_id": "selected-data",
                    "result_type": "data",
                    "rows": {"rows": [{"value": 9}]},
                    "structured": {"rows": [{"value": 9}]},
                }
            ]
        ),
    )
    legacy = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "app.services.ai.memory_service.memory_service.get_current_data_result",
        legacy,
    )
    runner = SimpleNamespace(
        conversation_id="conv-1",
        _current_user_id=lambda: 7,
    )

    result = await load_last_data_result(runner, preferred_result_id="selected-data")

    assert result["result_id"] == "selected-data"
    assert result["rows"] == {"rows": [{"value": 9}]}
    legacy.assert_not_awaited()


@pytest.mark.asyncio
async def test_chatbi_followup_loader_does_not_fall_back_to_current_for_missing_selection(monkeypatch):
    from app.services.ai.runners.chatbi.followup_data import load_last_data_result

    monkeypatch.setattr(
        "app.services.ai.memory_service.memory_service.get_reusable_result",
        AsyncMock(
            return_value={
                "result_id": "current-data",
                "result_type": "data",
                "structured": {"rows": [{"value": 1}]},
            }
        ),
    )
    monkeypatch.setattr(
        "app.services.ai.memory_service.memory_service.get_reusable_result_stack",
        AsyncMock(return_value=[]),
    )
    legacy = AsyncMock(return_value={"rows": [{"value": 2}]})
    monkeypatch.setattr(
        "app.services.ai.memory_service.memory_service.get_current_data_result",
        legacy,
    )
    legacy_data = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "app.services.ai.memory_service.memory_service.get_last_data_result",
        legacy_data,
    )
    runner = SimpleNamespace(
        conversation_id="conv-1",
        _current_user_id=lambda: 7,
    )

    result = await load_last_data_result(runner, preferred_result_id="missing-data")

    assert result is None
    legacy.assert_not_awaited()
    legacy_data.assert_awaited_once()


@pytest.mark.asyncio
async def test_chatbi_followup_loader_can_select_migrating_legacy_result(monkeypatch):
    from app.services.ai.reusable_result import normalize_legacy_data_result
    from app.services.ai.runners.chatbi.followup_data import load_last_data_result

    legacy = {
        "rows": {"rows": [{"value": 2}]},
        "saved_at": "2026-08-30T10:00:00+00:00",
    }
    selected_id = normalize_legacy_data_result(legacy)["result_id"]
    monkeypatch.setattr(
        "app.services.ai.memory_service.memory_service.get_reusable_result",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.services.ai.memory_service.memory_service.get_reusable_result_stack",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "app.services.ai.memory_service.memory_service.get_last_data_result",
        AsyncMock(return_value=legacy),
    )
    monkeypatch.setattr(
        "app.services.ai.memory_service.memory_service.get_current_data_result",
        AsyncMock(side_effect=AssertionError("legacy direct path should not be needed")),
    )
    runner = SimpleNamespace(conversation_id="conv-1", _current_user_id=lambda: 7)

    result = await load_last_data_result(runner, preferred_result_id=selected_id)

    assert result["result_id"] == selected_id
    assert result["result_type"] == "data"
