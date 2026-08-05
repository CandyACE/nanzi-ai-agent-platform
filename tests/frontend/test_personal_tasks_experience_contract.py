"""Contract: personal center embeds TaskCenter as 我的任务 without menu:task_center / element:task:manage."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PERSONAL_CENTER = ROOT / "frontend" / "src" / "views" / "PersonalCenter.vue"
TASK_CENTER = ROOT / "frontend" / "src" / "views" / "TaskCenter.vue"


def test_personal_center_exposes_tasks_tab_after_mcp():
    text = PERSONAL_CENTER.read_text(encoding="utf-8")
    assert "'tasks'" in text or '"tasks"' in text
    assert "我的任务" in text
    assert "TaskCenter" in text
    assert "personal-only" in text or "personalOnly" in text or "personal-only" in text.replace("_", "-")
    mcp_at = text.index("我的 MCP")
    tasks_at = text.index("我的任务")
    assert mcp_at < tasks_at


def test_task_center_supports_personal_only_owner_manage():
    text = TASK_CENTER.read_text(encoding="utf-8")
    assert "personalOnly" in text
    assert "我的任务" in text
    # personal center must not gate create/manage on element:task:manage
    assert "props.personalOnly" in text
    assert "element:task:manage" in text  # still used for full TaskCenter
    assert "isTaskOwner" in text
    assert "scopedTasks" in text