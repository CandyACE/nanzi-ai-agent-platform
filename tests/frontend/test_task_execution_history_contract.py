"""Contract: TaskCenter execution history tab for all users including personalOnly."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TASK_CENTER = ROOT / "frontend" / "src" / "views" / "TaskCenter.vue"
TASK_API = ROOT / "frontend" / "src" / "api" / "task.ts"
TASKS_ENDPOINT = ROOT / "app" / "api" / "v1" / "endpoints" / "tasks.py"


def test_task_api_exposes_execution_history():
    text = TASK_API.read_text(encoding="utf-8")
    assert "executionHistory" in text
    assert "/api/v1/tasks/execution-history" in text
    assert "TaskExecutionHistoryItem" in text


def test_task_center_history_tab_available_including_personal_only():
    text = TASK_CENTER.read_text(encoding="utf-8")
    assert "showHistoryTab" in text
    assert "mainViewTab" in text
    assert "执行记录" in text
    # 不再限制为仅管理员 / 排除 personalOnly
    assert "isAdmin.value && !props.personalOnly" not in text
    assert "fetchExecutionHistory" in text
    assert "historyQ" in text
    assert "historyStatus" in text
    assert "historyTaskId" in text
    assert "historyStartAt" in text
    assert "historyEndAt" in text
    assert "taskApi.executionHistory" in text
    assert "已删除任务" in text
    # 主 Tab 落在底部边框栏
    assert 'mainViewTab = \'history\'' in text or 'mainViewTab = "history"' in text
    assert "border-b border-gray-200" in text
    assert "bg-gray-100/80 p-0.5" not in text
    # 工作台可深链到执行记录 Tab
    assert "route.query.view" in text
    assert "'history'" in text


def test_backend_execution_history_scopes_non_admin():
    text = TASKS_ENDPOINT.read_text(encoding="utf-8")
    assert "/execution-history" in text
    assert "仅管理员可查看全局执行记录" not in text
    assert "owner_user_id" in text
    assert "is_admin" in text
    # 路由须注册在 /{task_id} 之前
    assert text.index("/execution-history") < text.index("/{task_id}")
