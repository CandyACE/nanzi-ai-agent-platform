# 自动路由阶段 SSE 展示 Implementation Plan

> **For agentic workers:** 本计划在当前会话内按步骤执行；每一步先写失败测试，再写最小实现。用户偏好不自动提交 Git，因此不包含自动提交步骤。

**Goal:** 将自动路由等待过程拆成用户可见的安全阶段，并通过现有 SSE `log` 协议实时显示在前端时间线中。

**Architecture:** 后端使用稳定的 `route:<stage>` 日志 ID，通过异步回调把路由阶段事件写入解析任务队列；`_run_chat_turn_stream` 并行等待解析结果和事件队列，因此首个路由阶段可以在目标专家解析完成前发送。`RouterService` 和 `AgentContextManager` 只发送安全状态，不发送原始路由 Prompt、候选列表或模型思考原文。前端复用 `addEmbedLogFromStream` 的同 ID 更新机制和 `ChatExecutionTimeline`。

**Tech Stack:** Python 3.11、FastAPI SSE generator、pytest、Vue 3、TypeScript、现有 `EmbedChat.vue`/`ChatExecutionTimeline.vue`。

---

### Task 1: 建立路由阶段事件契约并写失败测试

**Files:**
- Create: `app/services/ai/route_progress.py`
- Create: `tests/ai/test_route_progress.py`

- [ ] **Step 1: Write the failing test**

新增测试验证稳定 ID、用户安全标题和 pending/success 字段：

```python
import pytest

from app.services.ai.route_progress import build_route_stage_log


pytestmark = pytest.mark.no_infrastructure


def test_route_stage_log_uses_stable_id_and_safe_fields():
    event = build_route_stage_log(
        "candidate_catalog",
        "获取可用专家",
        status="pending",
    )

    assert event == {
        "type": "log",
        "id": "route:candidate_catalog",
        "title": "获取可用专家",
        "category": "router",
        "status": "pending",
    }
    assert "thought" not in event
    assert "candidates" not in event


def test_route_stage_log_keeps_same_id_for_completion_and_duration():
    event = build_route_stage_log(
        "candidate_catalog",
        "获取可用专家",
        status="success",
        execution_time_ms=12.5,
        details="已完成授权范围检查",
    )

    assert event["id"] == "route:candidate_catalog"
    assert event["status"] == "success"
    assert event["execution_time_ms"] == 12.5
    assert event["details"] == "已完成授权范围检查"


@pytest.mark.asyncio
async def test_emit_route_stage_forwards_only_route_log_payload():
    received = []

    async def receive(event):
        received.append(event)

    from app.services.ai.route_progress import emit_route_stage

    await emit_route_stage(receive, "router_model", "匹配目标专家", status="pending")

    assert received == [
        {
            "type": "log",
            "id": "route:router_model",
            "title": "匹配目标专家",
            "category": "router",
            "status": "pending",
        }
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest -q --confcutdir=tests/ai tests/ai/test_route_progress.py`

Expected: FAIL because `app.services.ai.route_progress` does not exist.

- [ ] **Step 3: Write minimal implementation**

在 `route_progress.py` 中定义：

```python
from collections.abc import Awaitable, Callable
from typing import Any

RouteProgressCallback = Callable[[dict[str, Any]], Awaitable[None]]


def build_route_stage_log(
    stage_id: str,
    title: str,
    *,
    status: str,
    details: str | None = None,
    execution_time_ms: float | None = None,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "type": "log",
        "id": f"route:{stage_id}",
        "title": title,
        "category": "router",
        "status": status,
    }
    if details:
        event["details"] = details
    if execution_time_ms is not None:
        event["execution_time_ms"] = execution_time_ms
    return event


async def emit_route_stage(
    callback: RouteProgressCallback | None,
    stage_id: str,
    title: str,
    *,
    status: str,
    details: str | None = None,
    execution_time_ms: float | None = None,
) -> None:
    if callback is None:
        return
    await callback(
        build_route_stage_log(
            stage_id,
            title,
            status=status,
            details=details,
            execution_time_ms=execution_time_ms,
        )
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest -q --confcutdir=tests/ai tests/ai/test_route_progress.py`

Expected: PASS.

### Task 2: 让路由服务产生阶段进度

**Files:**
- Modify: `app/services/ai/router_service.py:209-707`
- Modify: `app/services/ai/context_manager.py:48-159`
- Modify: `tests/ai/test_router_context.py`

- [ ] **Step 1: Write the failing test**

在 `test_router_context.py` 增加回调断言，验证正常模型路由至少发送候选目录、路由模型两个阶段，且不含原始思考字段：

```python
@pytest.mark.asyncio
async def test_router_emits_safe_progress_stages_without_raw_reasoning():
    router = RouterService()
    events = []
    agents = [
        {"id": "general-agent", "name": "general-chat", "description": "通用问答", "capabilities": ["chat"]},
        {"id": "data-agent", "name": "chat-bi", "description": "业务数据查询", "capabilities": ["data_query"]},
    ]

    mock_chat = AsyncMock()
    mock_chat.generate_structured_dict.return_value = {
        "agent_name": "general-chat",
        "confidence": 0.9,
        "secondary_agents": [],
        "intent": "GENERAL",
        "domain": "general",
        "thought": "内部路由理由不应进入进度事件",
    }

    async def on_progress(event):
        events.append(event)

    with patch.object(router, "_fetch_agents_from_db", new_callable=AsyncMock, return_value=agents), \
        patch.object(router, "_filter_agents_for_user", new_callable=AsyncMock, return_value=agents), \
        patch("app.services.ai.router_service.build_accessible_resource_catalog", new_callable=AsyncMock, return_value=""), \
        patch("app.services.ai.router_service.load_authorized_knowledge_catalog", new_callable=AsyncMock, return_value=None), \
        patch("app.services.ai.router_service.get_llm_async", new_callable=AsyncMock, return_value=object()), \
        patch("app.services.ai.router_service.chat_client_from_handle", return_value=mock_chat):
        result = await router.route_query("帮我写一段说明", on_progress=on_progress)

    assert result is not None
    assert [event["id"] for event in events] == [
        "route:candidate_catalog",
        "route:candidate_catalog",
        "route:router_model",
        "route:router_model",
    ]
    assert events[0]["status"] == "pending"
    assert events[1]["status"] == "success"
    assert events[2]["status"] == "pending"
    assert events[3]["status"] == "success"
    assert all("thought" not in event for event in events)

    assert "thought" not in events[3].get("details", "")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest -q --confcutdir=tests/ai tests/ai/test_router_context.py::test_router_emits_safe_progress_stages_without_raw_reasoning`

Expected: FAIL because `route_query()` does not accept `on_progress`.

- [ ] **Step 3: Write minimal implementation**

为 `RouterService.route_query()` 增加可选 `on_progress: RouteProgressCallback | None = None`，并按以下边界发送事件：

1. 进入候选专家读取/权限过滤前发送 `route:candidate_catalog` pending；完成过滤后发送 success。
2. 即将进入统一路由模型循环前发送 `route:router_model` pending。
3. 得到合法目标或安全 fallback 后发送 success；最终无法路由时发送 error。事件详情只写“已完成路由判断”或“已使用安全兜底”，不写 `thought`、完整候选清单、Prompt 或数据集名称。
4. 知识目录需要加载时，发送 `route:knowledge_catalog` pending/success；非知识问题不发送该步骤。

在 `AgentContextManager.resolve_agent_config()` 增加同名可选回调并传给 `router_service.route_query()`。显式专家路径不触发候选目录和路由模型事件。

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest -q --confcutdir=tests/ai tests/ai/test_route_progress.py tests/ai/test_router_context.py::test_router_emits_safe_progress_stages_without_raw_reasoning`

Expected: PASS.

### Task 3: 让 AgentService 在首个 SSE 前实时转发路由事件

**Files:**
- Modify: `app/services/ai/agent_service.py:2073-2187,2638-2685`
- Create: `tests/services/ai/test_route_progress_stream.py`

- [ ] **Step 1: Write the failing test**

新增测试验证解析任务发出的 pending 事件可以在解析结束前被流式转发，而不是等完整解析结束后一次性返回：

```python
import asyncio

import pytest

from app.services.ai.agent_service import AgentService


pytestmark = pytest.mark.no_infrastructure


@pytest.mark.asyncio
async def test_route_progress_is_forwarded_before_resolution_finishes(monkeypatch):
    service = AgentService()
    release = asyncio.Event()
    config = object()

    async def resolve(*, route_progress, **kwargs):
        await route_progress({
            "type": "log",
            "id": "route:candidate_catalog",
            "title": "获取可用专家",
            "category": "router",
            "status": "pending",
        })
        await release.wait()
        return config, None, 1.0, None

    monkeypatch.setattr(service, "_resolve_and_verify_agent", resolve)
    route_events = asyncio.Queue()

    task = service._start_route_resolution(
        route_events=route_events,
        resolve_kwargs={"messages": [], "user_query": "测试"},
    )
    event = await asyncio.wait_for(route_events.get(), timeout=0.1)
    assert event["id"] == "route:candidate_catalog"
    assert event["status"] == "pending"
    assert not task.done()
    release.set()
    result = await task
    assert result[0] is config
    assert result[1:] == (None, 1.0, None)
```

`_start_route_resolution()` 是实际生产辅助方法：接收事件队列和解析参数，给 `_resolve_and_verify_agent()` 注入回调并返回解析任务；`_run_chat_turn_stream()` 也使用同一方法，不能保留测试专用分支。

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest -q --confcutdir=tests/services/ai tests/services/ai/test_route_progress_stream.py::test_route_progress_is_forwarded_before_resolution_finishes`

Expected: FAIL because the progress-aware resolver/forwarder does not exist.

- [ ] **Step 3: Write minimal implementation**

在 `_resolve_and_verify_agent()` 增加可选 `route_progress` 参数，并在目标配置解析、最终权限校验前后发送共享阶段事件。新增实际辅助方法 `_start_route_resolution()`，然后在 `_run_chat_turn_stream()` 中：

```python
route_events: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
resolve_task = self._start_route_resolution(
    route_events=route_events,
    resolve_kwargs={
        "messages": messages,
        "agent_id": agent_id,
        "agent_name": agent_name,
        "version_id": version_id,
        "enable_multi_agent": enable_multi_agent,
        "user_info": user_info,
        "trace_buffer": trace_buffer,
        "user_query": user_query,
        "force_data_query": bool(metadata_dataset_ids),
        "conversation_id": conversation_id,
    },
)

while True:
    if not route_events.empty():
        yield await route_events.get()
        continue
    if resolve_task.done():
        break
    try:
        yield await asyncio.wait_for(route_events.get(), timeout=0.05)
    except asyncio.TimeoutError:
        continue

agent_config, route_details, route_elapsed_ms, err_msg = await resolve_task
```

实际代码应使用一个不会丢失超时取出的事件的等待循环；如果 `wait_for` 取到事件，立即 `yield`，如果超时则再次检查任务状态。解析任务异常必须先由 `await resolve_task` 抛出，不能吞掉。客户端断开时应取消未完成的解析任务并等待其结束，避免后台任务继续访问数据库或模型。

共享阶段事件：

- 指定专家：`route:target_config`、`route:target_permission`；
- 自动路由：路由服务产生的阶段，再补 `route:target_config`、`route:target_permission`；
- 权限失败：对应阶段发送 `error`，详情只写“目标专家权限校验失败”。

完成解析后保留现有 `router_log` 和意图日志，保证历史前端与审计兼容；新增阶段日志不携带路由原始理由。

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest -q --confcutdir=tests/services/ai tests/services/ai/test_route_progress_stream.py`

Expected: PASS.

### Task 4: 前端显示路由阶段并补契约测试

**Files:**
- Modify: `frontend/src/views/EmbedChat.vue:7167-7238`
- Modify: `frontend/src/components/chat/ChatExecutionTimeline.vue:441-455`
- Modify: `tests/frontend/test_embed_thought_stages.py`

- [ ] **Step 1: Write the failing test**

扩展前端契约测试，验证路由阶段标题会被归类为 `router`，并且前端沿用稳定 ID 更新逻辑：

```python
def test_route_progress_contract_uses_router_category_and_stable_ids():
    embed = (ROOT / "frontend/src/views/EmbedChat.vue").read_text(encoding="utf-8")
    timeline = (ROOT / "frontend/src/components/chat/ChatExecutionTimeline.vue").read_text(encoding="utf-8")

    assert 'data.id || Date.now() + Math.random()' in embed
    assert 'existingIdx = msg.logs.findIndex((l) => l.id === logId)' in embed
    assert 'category: "router"' in embed or 'category === "router"' in embed
    assert 'item.title.includes("获取可用专家")' in timeline
    assert 'item.category === "router"' in timeline
    assert 'item.status === "pending"' in timeline
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest -q --confcutdir=tests/frontend tests/frontend/test_embed_thought_stages.py::test_route_progress_contract_uses_router_category_and_stable_ids`

Expected: FAIL if the new route-specific contract is not present.

- [ ] **Step 3: Write minimal implementation**

前端保持现有 `addEmbedLogFromStream()` 的 ID 合并逻辑，只补充路由阶段的安全标题和图标映射：

- `获取可用专家` → `📚` 或 `🧭`；
- `匹配目标专家` → `🧠`；
- `校验目标专家权限` → `🔒`；
- `准备知识/数据资源` → `📋`。

路由阶段进入时让当前步骤标题显示在 `ChatThinkingHeader`，完成后保留耗时。不要在前端拼接或展示 `thought`、候选专家列表、完整 Prompt 等内部字段。

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest -q --confcutdir=tests/frontend tests/frontend/test_embed_thought_stages.py`

Expected: PASS.

### Task 5: 聚焦回归验证

**Files:**
- No new files.

- [ ] **Step 1: Run backend route-progress tests**

Run: `PYTHONPATH=. pytest -q --confcutdir=tests/ai tests/ai/test_route_progress.py tests/ai/test_router_context.py tests/ai/runtime/test_process_timeline_snapshot.py`

Expected: all selected tests PASS.

- [ ] **Step 2: Run AgentService stream tests**

Run: `PYTHONPATH=. pytest -q --confcutdir=tests/services/ai tests/services/ai/test_route_progress_stream.py tests/services/ai/test_context_compaction_event_persistence.py tests/services/ai/test_agent_service_model_query.py`

Expected: all selected tests PASS; any unrelated infrastructure failure must单独记录。

- [ ] **Step 3: Run frontend contract and type checks**

Run: `pytest -q --confcutdir=tests/frontend tests/frontend/test_embed_thought_stages.py`；随后在 `frontend/` 目录运行 `./node_modules/.bin/vue-tsc --noEmit`。

Expected: contract tests PASS and TypeScript check PASS。

- [ ] **Step 4: Check the diff**

Run: `git diff --check -- app/services/ai/route_progress.py app/services/ai/router_service.py app/services/ai/context_manager.py app/services/ai/agent_service.py frontend/src/views/EmbedChat.vue frontend/src/components/chat/ChatExecutionTimeline.vue tests/ai tests/services/ai tests/frontend`

Expected: no whitespace errors。不得运行 `./dev.sh`，不启动服务，不自动提交。

---

## Self-Review Checklist

- 路由模型原始 `thought`、完整候选目录、Prompt 和授权资源明细不会进入新增 SSE 事件。
- 自动路由和指定专家的事件只增加可观测性，不改变 `TurnDecision`、最终权限校验、Dispatcher 或 runner 行为。
- 同一个阶段始终使用同一个 `route:<stage>` ID，前端能正确更新 pending 到完成态。
- 路由任务异常、权限拒绝和客户端断开时不会留下无法回收的后台任务。
- 保留已有 `router_log`、`log` 和历史时间线回放兼容性。
