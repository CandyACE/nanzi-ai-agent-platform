# Todo 清单成功收尾兜底 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在任务正常成功结束时，由后端将当前轮 Todo 中剩余的 `pending` / `in_progress` 项统一收尾为 `completed`，避免模型忘记最后一次更新。

**Architecture:** 在时间线快照模块增加一个纯内存 Todo 收尾 helper，负责校验当前快照、原地更新状态并返回一次 `todo_update` 事件。AgentScope 运行时状态保存最近 Todo 快照，挂起恢复时先还原该快照。AgentService 仅在 `execution_status == "success"` 的普通执行、权限恢复和外部执行恢复路径调用该 helper，并在最终持久化前 yield 事件；其他状态不调用，保留原快照。

**Tech Stack:** Python 3.11、FastAPI 服务层、pytest、现有 `process_timeline_snapshot` 时间线快照协议。

---

### Task 1: 为成功收尾建立失败测试

**Files:**
- Modify: `tests/services/ai/test_agent_service_stream_content.py`
- Test: `tests/services/ai/test_agent_service_stream_content.py`

- [x] **Step 1: 写出成功收尾和非成功状态测试**

增加以下行为测试：

```python
def test_success_finalization_completes_remaining_todos_and_returns_update_event():
    state = [{
        "kind": "todo",
        "id": "todo_current",
        "title": "任务清单",
        "todos": [
            {"content": "已完成步骤", "status": "completed"},
            {"content": "遗漏步骤", "status": "in_progress"},
        ],
        "counts": {"pending": 0, "in_progress": 1, "completed": 1},
    }]

    event = _finalize_todo_success(state, execution_status="success")

    assert event == {
        "type": "todo_update",
        "todos": [
            {"content": "已完成步骤", "status": "completed"},
            {"content": "遗漏步骤", "status": "completed"},
        ],
        "counts": {"pending": 0, "in_progress": 0, "completed": 2},
    }
    assert _final_process_timeline(state)[0]["counts"] == {
        "pending": 0,
        "in_progress": 0,
        "completed": 2,
    }


def test_success_finalization_does_not_duplicate_already_completed_todos():
    state = [{
        "kind": "todo",
        "todos": [{"content": "已完成步骤", "status": "completed"}],
    }]

    assert _finalize_todo_success(state, execution_status="success") is None


@pytest.mark.parametrize(
    "execution_status",
    ["error", "cancelled", "awaiting_permission", "awaiting_external_execution", "awaiting_user"],
)
def test_non_success_finalization_preserves_todo_status(execution_status):
    state = [{
        "kind": "todo",
        "todos": [{"content": "未完成步骤", "status": "in_progress"}],
    }]

    assert _finalize_todo_success(state, execution_status=execution_status) is None
    assert state[0]["todos"][0]["status"] == "in_progress"
```

同时在 import 中加入 `_finalize_todo_success`。

- [x] **Step 2: 运行测试确认按预期失败**

Run: `PYTHONPATH=. venv/bin/python -m pytest tests/services/ai/test_agent_service_stream_content.py -q`

Expected: FAIL，原因是 `_finalize_todo_success` 尚不存在。

### Task 2: 实现时间线快照 Todo 收尾 helper

**Files:**
- Modify: `app/services/ai/runtime/agentscope/process_timeline_snapshot.py`
- Test: `tests/services/ai/test_agent_service_stream_content.py`

- [x] **Step 1: 实现最小原地收尾逻辑**

在 `_apply_todo_update` 后增加 `complete_todo_items`：

```python
def complete_todo_items(state: Optional[List[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
    """将当前轮最后一份 Todo 快照收尾，并返回实时更新事件。"""
    for item in reversed(state or []):
        if item.get("kind") != "todo":
            continue
        normalized = _normalize_todo_update(item)
        if normalized is None or not normalized["todos"]:
            return None
        if all(todo["status"] == "completed" for todo in normalized["todos"]):
            return None

        todos = [
            {"content": todo["content"], "status": "completed"}
            for todo in normalized["todos"]
        ]
        counts = {status: sum(todo["status"] == status for todo in todos) for status in TODO_STATUSES}
        item["todos"] = todos
        item["counts"] = counts
        return {"type": "todo_update", "todos": todos, "counts": counts}
    return None
```

- [x] **Step 2: 在 AgentService 增加状态门控 wrapper**

在 `app/services/ai/agent_service.py` 增加：

```python
def _finalize_todo_success(
    state: Optional[List[Dict[str, Any]]],
    *,
    execution_status: str,
) -> Optional[Dict[str, Any]]:
    if execution_status != "success":
        return None
    from app.services.ai.runtime.agentscope.process_timeline_snapshot import complete_todo_items

    return complete_todo_items(state)
```

- [x] **Step 3: 运行 Task 1 测试确认通过**

Run: `PYTHONPATH=. venv/bin/python -m pytest tests/services/ai/test_agent_service_stream_content.py -q`

Expected: PASS。

### Task 3: 接入普通执行和恢复执行的最终事件流

**Files:**
- Modify: `app/services/ai/agent_service.py:3214-3238`
- Modify: `app/services/ai/agent_service.py:3470-3495`
- Modify: `app/services/ai/agent_service.py:3735-3760`
- Test: `tests/services/ai/test_agent_service_stream_content.py`

- [x] **Step 1: 在普通执行最终统计前调用成功收尾**

在 `requires_tool_execution` 检查之后、token 汇总之前加入：

```python
todo_completion = _finalize_todo_success(
    (shared_state or {}).get("process_timeline"),
    execution_status=execution_status,
)
if todo_completion:
    yield todo_completion
```

这样外层 `chat_completion_stream` 会先把最终事件同步到实时 UI，再执行后续持久化。

- [x] **Step 2: 在权限恢复和外部执行恢复路径复用同一门控**

在两处恢复方法开始时从 pending stream state 还原最近 Todo 快照；执行流结束后、token 汇总前分别加入同样的 `todo_completion` 片段，使用各自的 `process_timeline_state` 和 `execution_status`。AgentScope runner 在转发 `todo_update` 队列事件时同步写入运行时状态，供 Redis/内存挂起快照保存。

- [x] **Step 3: 运行静态和 focused 回归**

Run:

```bash
PYTHONPATH=. venv/bin/python -m pytest \
  tests/services/ai/test_agent_service_stream_content.py \
  tests/ai/tools/test_todo_tools.py \
  tests/frontend/test_chat_shared_helpers_behavior.py -q
```

Expected: 全部通过。

### Task 4: 完成边界检查

**Files:**
- Modify: `docs/superpowers/specs/2026-08-22-todo-finalization-design.md` only if implementation details require clarification.

- [x] **Step 1: 检查差异和语法**

Run: `git diff --check`

Expected: 无输出。

Run: `PYTHONPATH=. venv/bin/python -m py_compile app/services/ai/agent_service.py app/services/ai/runtime/agentscope/process_timeline_snapshot.py tests/services/ai/test_agent_service_stream_content.py`

Expected: exit code 0。

- [x] **Step 2: 检查未授权范围**

确认只修改 Todo 收尾相关的后端文件和测试，不修改 Todo 触发规则、前端展示协议、工具状态枚举、数据库迁移或服务启动脚本。

- [x] **Step 3: 汇报结果**

报告变更文件、成功/非成功状态行为、测试命令与结果；不执行 commit。
