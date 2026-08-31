# 统一 Agent 超时配置 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让子代理整体委派超时和前端挂起步骤看门狗统一使用 `agent_max_toolcall_timeout` 的本次运行配置快照。

**Architecture:** API 层读取一次全局 Agent 工具超时，作为本次 SSE 的 `run_config` 事件下发，并写入 `request_observability` 传给 AgentService。AgentService 将该快照放入内部 AgentContext；子代理委派优先复用上下文快照，独立入口再回退到同一个全局配置读取器。前端共用 SSE 处理器保存快照，两个聊天页面的看门狗按消息快照计算阈值。

**Tech Stack:** Python 3.11、FastAPI、Pydantic、pytest、Vue 3、TypeScript、Vite、Node TypeScript transpile contract tests。

---

### Task 1: 让 AgentContext 能保存本次运行的超时快照

**Files:**
- Modify: `app/core/context.py:19-95`
- Modify: `app/services/ai/context_manager.py:166-320`
- Test: `tests/ai/test_sub_agent_delegation.py`

- [ ] **Step 1: Write the failing test**

在 `tests/ai/test_sub_agent_delegation.py` 增加：

```python
def test_agent_context_keeps_agent_toolcall_timeout_snapshot():
    context = AgentContext(
        agent_id="main-agent-id",
        agent_name="MainAgent",
        agent_max_toolcall_timeout_seconds=300.0,
    )

    assert context.agent_max_toolcall_timeout_seconds == 300.0
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/ai/test_sub_agent_delegation.py::test_agent_context_keeps_agent_toolcall_timeout_snapshot -q
```

Expected: FAIL because `AgentContext` does not yet define the snapshot field.

- [ ] **Step 3: Write minimal implementation**

在 `AgentContext` 增加可选字段：

```python
agent_max_toolcall_timeout_seconds: Optional[float] = None
```

在 `AgentContextManager.setup_context(...)` 增加同名可选参数，并在构造 `AgentContext(...)` 时写入：

```python
agent_max_toolcall_timeout_seconds=agent_max_toolcall_timeout_seconds,
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python3 -m pytest tests/ai/test_sub_agent_delegation.py::test_agent_context_keeps_agent_toolcall_timeout_snapshot -q
```

Expected: PASS。

### Task 2: 让子代理委派使用全局 `agent_max_toolcall_timeout`

**Files:**
- Modify: `app/services/ai/tools/agent_delegate_tool.py:438-448,757-791`
- Modify: `app/services/ai/agent_service.py:1261-1288,1670-1686,3825-3898`
- Test: `tests/ai/test_sub_agent_delegation.py`

- [ ] **Step 1: Write the failing test**

增加两个测试，分别验证独立入口读取全局配置、正常聊天上下文优先使用本次快照：

```python
@pytest.mark.asyncio
async def test_resolve_delegation_timeout_uses_global_agent_toolcall_config(monkeypatch):
    monkeypatch.setattr(
        "app.services.ai.tools.agent_delegate_tool.get_current_agent_context",
        lambda: None,
    )
    loader = AsyncMock(return_value=300.0)
    monkeypatch.setattr(
        "app.services.ai.runtime.agentscope.tool_timeout.load_agent_max_toolcall_timeout",
        loader,
    )

    assert await delegation_tool._resolve_delegation_timeout_seconds() == 300.0
    loader.assert_awaited_once()


@pytest.mark.asyncio
async def test_resolve_delegation_timeout_prefers_current_run_snapshot(monkeypatch):
    set_agent_context(
        AgentContext(
            agent_id="main-agent-id",
            agent_name="MainAgent",
            agent_max_toolcall_timeout_seconds=300.0,
        )
    )
    loader = AsyncMock(side_effect=AssertionError("should use run snapshot"))
    monkeypatch.setattr(
        "app.services.ai.runtime.agentscope.tool_timeout.load_agent_max_toolcall_timeout",
        loader,
    )

    try:
        assert await delegation_tool._resolve_delegation_timeout_seconds() == 300.0
    finally:
        set_agent_context(None)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest tests/ai/test_sub_agent_delegation.py::test_resolve_delegation_timeout_uses_global_agent_toolcall_config tests/ai/test_sub_agent_delegation.py::test_resolve_delegation_timeout_prefers_current_run_snapshot -q
```

Expected: FAIL because the resolver still reads `sub_agent_delegation_timeout_seconds` and the context has not yet been wired through the active run.

- [ ] **Step 3: Write minimal implementation**

将 `_resolve_delegation_timeout_seconds()` 改为：

```python
async def _resolve_delegation_timeout_seconds() -> float:
    current_context = get_current_agent_context()
    snapshot = getattr(current_context, "agent_max_toolcall_timeout_seconds", None)
    if snapshot is not None:
        from app.services.ai.runtime.agentscope.tool_timeout import parse_agent_max_toolcall_timeout

        return parse_agent_max_toolcall_timeout(snapshot)

    from app.services.ai.runtime.agentscope.tool_timeout import load_agent_max_toolcall_timeout

    return await load_agent_max_toolcall_timeout()
```

在 `AgentService.chat_completion_stream` 将 `request_observability["agent_max_toolcall_timeout"]` 解析后写入内部 `debug_options` 快照；在 `_run_chat_turn_stream` 的两处 `AgentContextManager.setup_context(...)` 传入该快照。子上下文构造时复制 `main_ctx.agent_max_toolcall_timeout_seconds`。

- [ ] **Step 4: Run focused delegation tests**

Run:

```bash
python3 -m pytest tests/ai/test_sub_agent_delegation.py -q
```

Expected: PASS。

### Task 3: 从聊天 SSE 下发同一份超时快照

**Files:**
- Modify: `app/api/v1/endpoints/chat.py:14-35,1429-1455,1559-1584`
- Modify: `app/services/ai/agent_service.py:1261-1288`
- Test: `tests/api/v1/test_chat_completions.py`

- [ ] **Step 1: Write the failing test**

在现有 `test_chat_completion_stream_sse_snapshot` 中 mock `load_agent_max_toolcall_timeout` 返回 `300.0`，并把期望事件首项改为：

```python
assert events[0] == {
    "type": "run_config",
    "agent_max_toolcall_timeout": 300,
}
```

同时保留现有后端流事件顺序断言在该事件之后。

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/api/v1/test_chat_completions.py::test_chat_completion_stream_sse_snapshot -q
```

Expected: FAIL because the endpoint does not currently send `run_config`。

- [ ] **Step 3: Write minimal implementation**

在 `create_chat_completion` 生成 `request_observability` 前读取：

```python
agent_max_toolcall_timeout_seconds = await load_agent_max_toolcall_timeout()
```

并加入：

```python
"agent_max_toolcall_timeout": int(agent_max_toolcall_timeout_seconds),
```

在流式 `sse_generator()` 首个循环前发送：

```python
yield "data: " + json.dumps(
    {
        "type": "run_config",
        "agent_max_toolcall_timeout": int(agent_max_toolcall_timeout_seconds),
    },
    ensure_ascii=False,
) + "\\n\\n"
```

AgentService 使用 `request_observability` 中的该值设置当前运行快照，未从 API 层进入时才回退调用既有全局读取器。

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python3 -m pytest tests/api/v1/test_chat_completions.py::test_chat_completion_stream_sse_snapshot -q
```

Expected: PASS。

### Task 4: 让共用前端 SSE 处理器和看门狗使用快照

**Files:**
- Modify: `frontend/src/utils/agentscopeSseHandlers.ts:93-136,810-900`
- Test: `tests/frontend/test_chat_shared_helpers_behavior.py`
- Test: `tests/frontend/test_agent_timeout_watchdog_contract.py`

- [ ] **Step 1: Write the failing tests**

在 `test_chat_shared_helpers_behavior.py` 增加 Node 行为测试：

```python
def test_run_config_event_sets_message_timeout_snapshot():
    result = _run_typescript(
        "frontend/src/utils/agentscopeSseHandlers.ts",
        """
const msg = { content: '' };
const consumed = api.dispatchAgentscopeStreamEvent(
  msg,
  { type: 'run_config', agent_max_toolcall_timeout: 300 },
  () => {}
);
return { consumed, timeout: msg.agentMaxToolcallTimeoutSeconds };
""",
    )
    assert result == {"consumed": True, "timeout": 300}
```

再增加看门狗行为测试：同一条 pending 日志在 300 秒前保持 pending，达到 300 秒后才变为 error；无快照时 180 秒兼容兜底仍有效。

在 `test_agent_timeout_watchdog_contract.py` 增加源码契约断言，确认不再存在 `staleMs = 120_000`，且 `markStalePendingStreamLogs` 会读取消息超时字段。

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest tests/frontend/test_chat_shared_helpers_behavior.py tests/frontend/test_agent_timeout_watchdog_contract.py -q
```

Expected: FAIL because `AgentStreamMessage` 没有超时快照字段，事件处理器不会消费 `run_config`，看门狗仍使用固定 180 秒。

- [ ] **Step 3: Write minimal implementation**

在 `AgentStreamMessage` 增加：

```ts
agentMaxToolcallTimeoutSeconds?: number;
```

增加安全归一化和默认值：

```ts
export const DEFAULT_AGENT_MAX_TOOLCALL_TIMEOUT_SECONDS = 180;

export function resolveAgentMaxToolcallTimeoutMs(
  msg: AgentStreamMessage,
  fallbackMs = DEFAULT_AGENT_MAX_TOOLCALL_TIMEOUT_SECONDS * 1000,
): number {
  const seconds = Number(msg.agentMaxToolcallTimeoutSeconds);
  return Number.isFinite(seconds) && seconds > 0 ? seconds * 1000 : fallbackMs;
}
```

将 `markStalePendingStreamLogs` 的第三个参数改为可选；没有显式传入时调用 `resolveAgentMaxToolcallTimeoutMs(msg)`，提示文案使用实际秒数。

在 `dispatchAgentscopeStreamEvent` 增加：

```ts
case "run_config": {
  const seconds = Number(data.agent_max_toolcall_timeout);
  if (Number.isFinite(seconds) && seconds > 0) {
    msg.agentMaxToolcallTimeoutSeconds = seconds;
  }
  return true;
}
```

- [ ] **Step 4: Run frontend behavior and contract tests**

Run:

```bash
python3 -m pytest tests/frontend/test_chat_shared_helpers_behavior.py tests/frontend/test_agent_timeout_watchdog_contract.py -q
```

Expected: PASS。

### Task 5: 完成回归验证和代码审查

**Files:**
- Test: `tests/ai/test_sub_agent_delegation.py`
- Test: `tests/api/v1/test_chat_completions.py`
- Test: `tests/frontend/test_chat_shared_helpers_behavior.py`
- Test: `tests/frontend/test_agent_timeout_watchdog_contract.py`

- [ ] **Step 1: Run backend focused tests**

```bash
python3 -m pytest tests/ai/test_sub_agent_delegation.py tests/api/v1/test_chat_completions.py -q
```

- [ ] **Step 2: Run frontend contract tests and type check**

```bash
python3 -m pytest --confcutdir=tests/frontend tests/frontend/test_chat_shared_helpers_behavior.py tests/frontend/test_agent_timeout_watchdog_contract.py -q
cd frontend && ./node_modules/.bin/vue-tsc --noEmit
```

- [ ] **Step 3: Run diff checks**

```bash
git diff --check
git status --short
```

只确认本次修改文件，不改动工作区中用户已有的 `app/api/v1/endpoints/fs.py`、`app/utils/fs_access.py` 及其他未纳入本任务的文件。

- [ ] **Step 4: Request code review**

完成测试后，基于本次实现提交前后的 commit 范围请求代码审查，重点检查：配置快照是否越过用户输入边界、前端看门狗是否仍有隐藏固定阈值、超时是否误取消后台任务、以及旧 SSE 事件兼容性。
