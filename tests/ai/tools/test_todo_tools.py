import asyncio

import pytest

from app.core.context import AgentContext
from app.services.ai.tools import todo_tools


pytestmark = pytest.mark.no_infrastructure


def _context(queue=None):
    return AgentContext(
        agent_id="general-agent",
        agent_name="GeneralAgent",
        event_queue=queue,
    )


@pytest.mark.asyncio
async def test_todo_write_replaces_full_list_and_emits_json_safe_snapshot(monkeypatch):
    queue = asyncio.Queue()
    context = _context(queue)
    monkeypatch.setattr(todo_tools, "get_current_agent_context", lambda: context)

    result = await todo_tools.todo_write.ainvoke(
        {
            "todos": [
                {"content": "  检索知识库  ", "status": "completed"},
                {"content": "整理答案", "status": "in_progress"},
                {"content": "生成说明", "status": "pending"},
            ]
        }
    )

    assert result == {
        "todos": [
            {"content": "检索知识库", "status": "completed"},
            {"content": "整理答案", "status": "in_progress"},
            {"content": "生成说明", "status": "pending"},
        ],
        "counts": {"pending": 1, "in_progress": 1, "completed": 1},
    }
    assert queue.get_nowait() == {
        "type": "todo_update",
        "todos": result["todos"],
        "counts": result["counts"],
    }
    assert context.todo_snapshot == {
        "type": "todo_update",
        "todos": result["todos"],
        "counts": result["counts"],
    }


@pytest.mark.asyncio
async def test_todo_write_accepts_empty_list_to_clear_without_event_queue(monkeypatch):
    monkeypatch.setattr(todo_tools, "get_current_agent_context", lambda: _context())

    result = await todo_tools.todo_write.ainvoke({"todos": []})

    assert result == {
        "todos": [],
        "counts": {"pending": 0, "in_progress": 0, "completed": 0},
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (
            {"todos": [{"content": "", "status": "pending"}]},
            "任务描述不能为空",
        ),
        (
            {
                "todos": [
                    {"content": "同一任务", "status": "pending"},
                    {"content": "同一任务", "status": "completed"},
                ]
            },
            "任务描述不能重复",
        ),
        (
            {"todos": [{"content": "任务", "status": "unknown"}]},
            "status",
        ),
        (
            {"todos": [{"content": "任务", "status": "pending", "id": "x"}]},
            "额外字段",
        ),
        (
            {
                "todos": [
                    {"content": str(index), "status": "pending"}
                    for index in range(21)
                ]
            },
            "不能超过 20 项",
        ),
        (
            {"todos": [{"content": "x" * 201, "status": "pending"}]},
            "不能超过 200 个字符",
        ),
    ],
)
async def test_todo_write_rejects_invalid_full_list(monkeypatch, payload, message):
    monkeypatch.setattr(todo_tools, "get_current_agent_context", lambda: _context())

    with pytest.raises(ValueError, match=message):
        await todo_tools.todo_write.ainvoke(payload)


def test_todo_write_schema_forbids_unknown_item_fields():
    schema = todo_tools.todo_write.args_schema.model_json_schema()

    item_schema = schema["$defs"]["TodoItem"]
    assert item_schema["additionalProperties"] is False
    assert set(item_schema["properties"]) == {"content", "status"}
