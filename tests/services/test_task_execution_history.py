"""任务执行记录：管理员看全部，普通用户仅看自己的。"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1.endpoints import tasks as tasks_endpoint
from app.services.task_center_service import TaskCenterService

pytestmark = pytest.mark.no_infrastructure


def _history_row(**overrides):
    row = MagicMock()
    row.id = overrides.get("id", 1)
    row.trace_id = overrides.get("trace_id", "trace-abc")
    row.query = overrides.get("query", "跑巡检")
    row.summary = overrides.get("summary", "完成")
    row.status = overrides.get("status", "success")
    row.execution_time_ms = overrides.get("execution_time_ms", 120.0)
    row.created_at = overrides.get("created_at", datetime(2026, 8, 5, 10, 0, 0))
    row.conversation_id = overrides.get("conversation_id", "task_conv_abcdef123456")
    row.username = overrides.get("username", "alice")
    row.agent_id = overrides.get("agent_id", "agent-1")
    return row


def _task_row(**overrides):
    task = MagicMock()
    task.id = overrides.get("id", 7)
    task.name = overrides.get("name", "PUE日报")
    task.agent_id = overrides.get("agent_id", "agent-1")
    task.user_id = overrides.get("user_id", 3)
    task.conversation_id = overrides.get("conversation_id", "task_conv_abcdef123456")
    return task


@pytest.mark.asyncio
async def test_list_execution_history_maps_task_and_excludes_plain_chat():
    db = AsyncMock()
    task = _task_row()
    run_row = _history_row(conversation_id="task_conv_abcdef123456_run_deadbeefcafe")

    task_result = MagicMock()
    task_result.all.return_value = [(task, "张三", "alice", "巡检助手")]
    hist_count = MagicMock()
    hist_count.scalar.return_value = 1
    hist_rows = MagicMock()
    hist_rows.scalars.return_value.all.return_value = [run_row]

    db.execute = AsyncMock(side_effect=[task_result, hist_count, hist_rows])

    items, total = await TaskCenterService.list_execution_history(
        db, page=1, page_size=20, is_admin=True
    )
    assert total == 1
    assert items[0]["task_id"] == 7
    assert items[0]["task_name"] == "PUE日报"
    assert items[0]["creator_name"] == "张三"
    assert items[0]["agent_name"] == "巡检助手"
    assert items[0]["trace_id"] == "trace-abc"


@pytest.mark.asyncio
async def test_list_execution_history_filters_by_task_id_status_and_q():
    db = AsyncMock()
    task = _task_row(id=9, name="周报", conversation_id="task_conv_zzzzzzzzzzzz")
    row = _history_row(
        id=2,
        status="failed",
        conversation_id="task_conv_zzzzzzzzzzzz_run_111111111111",
        summary="失败原因",
    )
    task_result = MagicMock()
    task_result.all.return_value = [(task, None, "bob", "助手")]
    hist_count = MagicMock()
    hist_count.scalar.return_value = 1
    hist_rows = MagicMock()
    hist_rows.scalars.return_value.all.return_value = [row]
    db.execute = AsyncMock(side_effect=[task_result, hist_count, hist_rows])

    items, total = await TaskCenterService.list_execution_history(
        db,
        task_id=9,
        status="failed",
        q="周报",
        is_admin=True,
    )
    assert total == 1
    assert items[0]["task_id"] == 9
    assert items[0]["status"] == "failed"


@pytest.mark.asyncio
async def test_list_execution_history_unknown_task_id_returns_empty():
    db = AsyncMock()
    task_result = MagicMock()
    task_result.all.return_value = []
    db.execute = AsyncMock(return_value=task_result)
    items, total = await TaskCenterService.list_execution_history(
        db, task_id=999, is_admin=True
    )
    assert items == []
    assert total == 0
    assert db.execute.await_count == 1


@pytest.mark.asyncio
async def test_list_execution_history_non_admin_without_owner_returns_empty():
    db = AsyncMock()
    items, total = await TaskCenterService.list_execution_history(
        db, is_admin=False, owner_user_id=None
    )
    assert items == []
    assert total == 0
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_list_execution_history_non_admin_scopes_to_owner_tasks():
    db = AsyncMock()
    task = _task_row(user_id=3)
    run_row = _history_row(conversation_id="task_conv_abcdef123456_run_deadbeefcafe")
    task_result = MagicMock()
    task_result.all.return_value = [(task, "张三", "alice", "巡检助手")]
    hist_count = MagicMock()
    hist_count.scalar.return_value = 1
    hist_rows = MagicMock()
    hist_rows.scalars.return_value.all.return_value = [run_row]
    db.execute = AsyncMock(side_effect=[task_result, hist_count, hist_rows])

    items, total = await TaskCenterService.list_execution_history(
        db, is_admin=False, owner_user_id=3
    )
    assert total == 1
    assert items[0]["task_id"] == 7
    # 非管理员不会用宽泛 task_conv_%，只扫自己任务会话
    hist_stmt = db.execute.await_args_list[1].args[0]
    compiled = str(hist_stmt.compile(compile_kwargs={"literal_binds": False}))
    assert "task_conv_%" not in compiled or "_run_%" in compiled


@pytest.mark.asyncio
async def test_execution_history_endpoint_user_ok_scoped():
    db = AsyncMock()
    with patch.object(
        TaskCenterService,
        "list_execution_history",
        AsyncMock(return_value=([], 0)),
    ) as service:
        resp = await tasks_endpoint.list_execution_history(
            page=1,
            page_size=20,
            status=None,
            task_id=None,
            q=None,
            start_at=None,
            end_at=None,
            user_info={"user_id": 42, "role": "user"},
            db=db,
        )
    assert resp.data.total == 0
    assert service.await_args.kwargs["is_admin"] is False
    assert service.await_args.kwargs["owner_user_id"] == 42


@pytest.mark.asyncio
async def test_execution_history_endpoint_admin_ok():
    db = AsyncMock()
    with patch.object(
        TaskCenterService,
        "list_execution_history",
        AsyncMock(
            return_value=(
                [
                    {
                        "id": 1,
                        "trace_id": "t1",
                        "query": "q",
                        "summary": "s",
                        "status": "success",
                        "execution_time_ms": 10,
                        "created_at": datetime(2026, 8, 5),
                        "conversation_id": "task_conv_x",
                        "username": "a",
                        "task_id": 1,
                        "task_name": "n",
                        "agent_id": "ag",
                        "agent_name": "Agent",
                        "user_id": 1,
                        "creator_name": "c",
                    }
                ],
                1,
            )
        ),
    ) as service:
        resp = await tasks_endpoint.list_execution_history(
            page=1,
            page_size=20,
            status=None,
            task_id=None,
            q=None,
            start_at=None,
            end_at=None,
            user_info={"user_id": 1, "role": "admin"},
            db=db,
        )
    assert resp.data.total == 1
    assert resp.data.items[0].task_name == "n"
    assert service.await_args.kwargs["is_admin"] is True
    assert service.await_args.kwargs["owner_user_id"] is None
