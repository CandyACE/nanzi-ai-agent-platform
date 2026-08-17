# 批量子代理委派 Implementation Plan

> **For agentic workers:** Implement this plan task-by-task with TDD. Keep the existing `sub_agent_call` contract unchanged and do not commit unless explicitly requested.

**Goal:** 新增一个批量委派工具，让主智能体一次提交多个独立子代理任务并行执行，同时按请求顺序返回结果。

**Architecture:** 保留现有 `sub_agent_call` 作为单次串行委派入口，批量工具复用它的目标解析、子会话创建、权限/工具过滤、超时、取消和结构化输出校验。新增 `sub_agent_batch_call` 接收 1-4 个调用项，在工具层创建独立 asyncio 任务并发运行，使用输入顺序组装结构化结果；每项使用独立 Trace buffer，单个任务失败、超时或被拒绝只影响对应结果，父任务取消时传播取消到所有未完成子任务。

**Tech Stack:** Python 3.11+, Pydantic 2, asyncio, AgentScope runtime, pytest.

---

### Task 1: Define the batch protocol

**Files:**
- Modify: `app/services/ai/tools/agent_delegate_tool.py`
- Test: `tests/ai/test_sub_agent_delegation.py`

- [x] Add a failing schema test for `sub_agent_batch_call` with `calls`, per-call `agent_name/query`, and optional per-call `max_depth/tool_filter/output_schema`.
- [x] Add a failing validation test for empty batches and batches larger than four calls.
- [x] Define `BatchSubAgentCall` and `BatchSubAgentArgs` models and return a JSON result containing `status`, `results`, `completed_count`, and `failed_count`.

### Task 2: Extract reusable single-call execution

**Files:**
- Modify: `app/services/ai/tools/agent_delegate_tool.py`
- Test: `tests/ai/test_sub_agent_delegation.py`

- [x] Add a failing test that a batch item preserves its own child session ID, parent lineage, tool filter, timeout, and structured-output validation.
- [x] Reuse the existing single delegation body through `sub_agent_call.func`; keep the public `sub_agent_call` text response unchanged and isolate each batch item's Trace buffer.
- [ ] Keep the existing self-delegation, duplicate-call, per-agent attempt, permission, timeout, and nested-depth guards active for each batch item.

### Task 3: Run batch items concurrently

**Files:**
- Modify: `app/services/ai/tools/agent_delegate_tool.py`
- Test: `tests/ai/test_sub_agent_delegation.py`

- [x] Add a failing timing/order test proving two independent items overlap but the returned `results` list follows input order.
- [x] Implement an `asyncio.gather`-based batch runner with a four-item limit; use per-item error results rather than aborting the whole batch.
- [x] On parent cancellation, cancel and await every unfinished child task, close child async generators, and re-raise `CancelledError`.

### Task 4: Register the batch capability

**Files:**
- Modify: `app/services/ai/tools/registry.py`
- Modify: `app/services/ai/runtime/agentscope/tools.py`
- Modify: `app/services/ai/tool_policy.py`
- Modify: `app/services/ai/agent_prompts.py`
- Test: `tests/ai/test_tool_capability_seam.py`
- Test: `tests/ai/tools/test_agent_delegate_tool.py` or `tests/ai/test_sub_agent_delegation.py`

- [x] Add failing tests that the batch tool is visible only where `sub_agent_call` is available and uses the same delegation permission scope.
- [x] Register `sub_agent_batch_call` as a system delegation tool without changing the existing tool name or configured-tool behavior.
- [x] Add prompt guidance telling the model to use the batch tool only for independent tasks and to use single delegation for dependent tasks.

### Task 5: Documentation and regression verification

**Files:**
- Modify: `tests/CHECKLIST.md`
- Modify: `docs/superpowers/plans/2026-08-17-independent-subagent-session-plan.md`
- Modify: `docs/superpowers/plans/2026-08-17-subagent-delegation-protocol.md`

- [ ] Document input-order result semantics, four-item concurrency limit, failure isolation, and cancellation behavior.
- [x] Run focused delegation/capability tests, Python compilation, and `git diff --check`.
- [ ] Run the existing sub-agent regression suite and report unrelated baseline failures separately.
