# 独立子代理会话 Implementation Plan

> **For agentic workers:** Implement this plan task-by-task with TDD. Keep unrelated worktree changes intact and do not commit unless explicitly requested.

**Goal:** 为一次性 `sub_agent_call` 创建独立的子会话命名空间，隔离会话级读取/写入，同时保留显式任务、权限、数据集和父子追踪关联。

批量委派中的每个调用项复用同一独立子会话规则；批量工具本身不共享子代理会话历史。

**Architecture:** 每次通过目标检查和重复委派检查的子代理生成唯一 `child_session_id`。子 Executor 使用该 ID 作为 `conversation_id`，父会话 ID 保存在 `parent_conversation_id` 中；父子仍共享实时 trace/event queue 和 grounding ledger，以保持现有主页面展示和证据回流。

**Tech Stack:** Python 3.11+, Pydantic 2, pytest, AgentContext, AgentDispatcher, Redis-backed conversation services.

---

### Task 1: Extend the session lineage protocol

**Files:**
- Modify: `app/services/ai/subagent_protocol.py`
- Test: `tests/ai/test_subagent_contract.py`

- [x] Add `parent_conversation_id` and `child_session_id` to `SubAgentRequest`, plus parent/child session lineage to `SubAgentResult`.
- [x] Keep metadata JSON-safe and do not add raw parent history or credentials.
- [x] Preserve the existing text returned by `to_tool_text()`.

### Task 2: Add request-scoped session fields

**Files:**
- Modify: `app/core/context.py`
- Test: `tests/ai/test_sub_agent_delegation.py`

- [x] Add `parent_conversation_id` and `child_session_id` to `AgentContext`.
- [x] Assert that a delegated executor receives only the explicit query as history and a child conversation ID distinct from the parent.

### Task 3: Route the delegated Executor through the child session

**Files:**
- Modify: `app/services/ai/tools/agent_delegate_tool.py`
- Test: `tests/ai/test_sub_agent_delegation.py`

- [x] Generate one child session ID only after target, filter, and duplicate-call checks pass.
- [x] Set the child context `conversation_id` to the child ID and preserve the parent ID in `parent_conversation_id`.
- [x] Pass the child ID to `AgentDispatcher` and include it in lifecycle metadata and terminal results.
- [x] Keep parent permissions, explicit dataset scope, shared evidence ledger, and live trace forwarding unchanged.

### Task 4: Document the first independent-session boundary

**Files:**
- Modify: `docs/superpowers/specs/2026-08-17-subagent-delegation-protocol-design.md`
- Modify: `docs/superpowers/plans/2026-08-17-subagent-delegation-protocol.md`
- Modify: `tests/CHECKLIST.md` only if the existing sub-agent checklist needs the new invariant.

- [x] Document that child session-scoped services use `child_session_id` and cannot implicitly read the parent conversation namespace.
- [x] Document the intentional shared surfaces: live trace queue, trace buffer, and grounding evidence ledger.
- [x] State that durable child transcript/replay APIs remain a later phase.

### Task 5: Verify the isolated-session path

- [x] Run `PYTHONPATH=. pytest -q tests/ai/test_subagent_contract.py tests/ai/test_sub_agent_delegation.py` — 43 passed.
- [x] Run `PYTHONPYCACHEPREFIX=/tmp/nanzi-pycache python3 -m compileall -q app/services/ai/subagent_protocol.py app/core/context.py app/services/ai/tools/agent_delegate_tool.py` — passed.
- [x] Run focused Ruff on changed protocol/context files and `git diff --check` — `git diff --check` passed; Ruff retains three pre-existing diagnostics in `agent_delegate_tool.py`.

The broader delegation/runtime regression also passed: 71 tests covering delegation contracts, cancellation, and AgentScope tooling.
