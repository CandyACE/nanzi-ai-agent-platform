"""Model-facing task checklist state for multi-step agent work."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from app.core.context import get_current_agent_context
from app.services.ai.tools.tool_compat import BaseTool


TodoStatus = Literal["pending", "in_progress", "completed"]
MAX_TODOS = 20
MAX_TODO_CONTENT_LENGTH = 200


class TodoItem(BaseModel):
    """One model-maintained task in the current execution checklist."""

    model_config = ConfigDict(extra="forbid")

    content: str = Field(description="任务描述，简短且可执行")
    status: TodoStatus = Field(description="pending、in_progress 或 completed")

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        content = str(value or "").strip()
        if not content:
            raise ValueError("任务描述不能为空")
        if len(content) > MAX_TODO_CONTENT_LENGTH:
            raise ValueError(f"任务描述不能超过 {MAX_TODO_CONTENT_LENGTH} 个字符")
        return content


class TodoWriteArgs(BaseModel):
    """Arguments accepted by the full-list replacement tool."""

    model_config = ConfigDict(extra="forbid")

    todos: list[TodoItem] = Field(
        description="完整任务清单；每次调用会整体替换之前的清单",
    )

    @field_validator("todos")
    @classmethod
    def validate_size(cls, value: list[TodoItem]) -> list[TodoItem]:
        if len(value) > MAX_TODOS:
            raise ValueError(f"任务清单不能超过 {MAX_TODOS} 项")
        return value

    @model_validator(mode="after")
    def validate_unique_content(self) -> "TodoWriteArgs":
        contents = [item.content for item in self.todos]
        if len(contents) != len(set(contents)):
            raise ValueError("任务描述不能重复")
        return self


def _counts(todos: list[TodoItem]) -> dict[str, int]:
    return {
        "pending": sum(item.status == "pending" for item in todos),
        "in_progress": sum(item.status == "in_progress" for item in todos),
        "completed": sum(item.status == "completed" for item in todos),
    }


class TodoWriteTool(BaseTool):
    """Replace the current main-agent task list and notify the live UI."""

    name = "todo_write"
    description = (
        "记录和更新当前任务清单。仅当请求包含多个步骤、多个工具或子代理、"
        "前后依赖或文件生成时使用；单步问答、单次检索和单次查询不要使用。"
        "每次调用发送完整清单，任务完成、失败或取消后更新对应状态。"
    )
    args_schema = TodoWriteArgs
    is_read_only = True
    evidence_inference_disabled = True

    async def ainvoke(self, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            args = TodoWriteArgs.model_validate(arguments or {})
        except ValidationError as exc:
            error = exc.errors()[0]
            if error.get("type") == "extra_forbidden":
                raise ValueError("任务清单包含额外字段") from exc
            if error.get("type") == "literal_error":
                raise ValueError("status 必须是 pending、in_progress 或 completed") from exc
            raise ValueError(str(error.get("msg") or "任务清单入参无效")) from exc
        todos = [item.model_dump(mode="json") for item in args.todos]
        counts = _counts(args.todos)
        event = {
            "type": "todo_update",
            "todos": todos,
            "counts": counts,
        }
        context = get_current_agent_context()
        event_queue = getattr(context, "event_queue", None) if context else None
        if event_queue is not None:
            try:
                event_queue.put_nowait(event)
            except Exception:
                # The checklist is auxiliary UI state; a closed or full UI
                # queue must not turn a valid bookkeeping call into a task failure.
                pass
        return {"todos": todos, "counts": counts}


todo_write = TodoWriteTool()


__all__ = [
    "MAX_TODOS",
    "MAX_TODO_CONTENT_LENGTH",
    "TodoItem",
    "TodoStatus",
    "TodoWriteArgs",
    "TodoWriteTool",
    "todo_write",
]
