# NanZi 通用任务清单工具 Implementation Plan

> **For agentic workers:** Implement this plan task-by-task with TDD. Preserve unrelated worktree changes and do not stage or commit unless explicitly requested.

**Goal:** Add a built-in `todo_write` tool for the main General Agent, stream its full-list task state through the existing AgentScope execution timeline, and render the latest checklist in AgentDebug and EmbedChat without adding a database table.

**Architecture:** The tool validates and emits a complete todo snapshot through the current `AgentContext.event_queue`. The existing `AgentService` stream reducer persists that snapshot inside `process_timeline`, so live SSE and history hydration use one representation. `ChatTodoCard` renders the latest snapshot as an independent sibling below the thinking/execution card, keeping it near the newest execution position while the thought trace grows. Tool registration, visibility, prompt guidance, and tool metadata remain in the current registry/capability seams; the main General Agent's tool preflight gives structurally multi-step requests a first-call `todo_write` opportunity, then releases normal model tool selection. ChatBI's domain task plan and subagent protocol remain unchanged.

**Implementation status:** Implemented through the runtime queue, AgentService timeline finalization, shared SSE dispatcher, history hydration, the AgentDebug/EmbedChat sibling card, and the main-General multi-step tool preflight. Focused backend and TypeScript checks pass; two pre-existing frontend contract failures remain in unrelated template/log assertions.

The task card now has local expand/collapse and close controls. It automatically collapses when the latest non-empty list is fully completed; these UI states do not modify the persisted todo snapshot.

**Tech Stack:** Python 3.11+, Pydantic, pytest, AgentScope runtime, FastAPI SSE contracts, Vue 3 + TypeScript, existing `process_timeline` utilities and `ChatExecutionTimeline`.

---

### Task 1: Add the todo tool contract and validation tests

**Files:**
- Create: `app/services/ai/tools/todo_tools.py`
- Test: `tests/ai/tools/test_todo_tools.py`

- [ ] **Step 1: Write failing tests** for a valid full-list replacement, empty-list clearing, normalized counts, duplicate rejection, blank-content rejection, invalid status rejection, unknown-field rejection, maximum 20 items, and maximum 200 characters per item.

  The tests must invoke the callable through the same `AgentContext`/tool path used by runtime tools. A successful call must return the normalized list and counts; invalid input must raise a stable validation error before an event is emitted.

- [ ] **Step 2: Run the focused tests and confirm the expected failure.**

  ```sh
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. pytest -q tests/ai/tools/test_todo_tools.py
  ```

  Expected: FAIL because `todo_tools.py` and `todo_write` do not exist.

- [ ] **Step 3: Implement the minimal tool contract.**

  Define `todo_write(todos)` with the repository's existing tool decorator/schema convention. Validate the full list, trim item content, reject empty or duplicate content, enforce the item and content limits, and return:

  ```python
  {
      "todos": [{"content": "...", "status": "pending"}],
      "counts": {"pending": 1, "in_progress": 0, "completed": 0},
  }
  ```

  Do not emit a stream event until validation succeeds. Allow an empty list and return zero counts.

- [ ] **Step 4: Run the focused tests and confirm they pass.**

  ```sh
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. pytest -q tests/ai/tools/test_todo_tools.py
  ```

### Task 2: Emit the live todo snapshot through the existing runtime queue

**Files:**
- Modify: `app/services/ai/tools/todo_tools.py`
- Test: `tests/ai/tools/test_todo_tools.py`

- [ ] **Step 1: Add failing tests** that attach an `asyncio.Queue` to `AgentContext.event_queue`, execute `todo_write`, and assert one `todo_update` payload containing the full list and snake_case counts. Add a test with no event queue asserting that the tool still succeeds without emitting an event.

- [ ] **Step 2: Run the new tests and confirm the event is missing.**

  ```sh
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. pytest -q tests/ai/tools/test_todo_tools.py -k event
  ```

- [ ] **Step 3: Emit the event after successful validation.**

  Use the current agent context lookup and `put_nowait` when a queue exists. The event must be JSON-safe and must not include credentials, raw prompt text, trace buffers, or evidence metadata. Keep the tool result independent from UI availability.

- [ ] **Step 4: Run the focused tool tests again.**

  ```sh
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. pytest -q tests/ai/tools/test_todo_tools.py
  ```

### Task 3: Register and expose the built-in tool only to the main General Agent

**Files:**
- Modify: `app/services/ai/tools/registry.py`
- Modify: `app/services/ai/runners/assistant_agent_runner.py`
- Modify: `app/services/ai/agent_prompts.py`
- Modify: `app/services/ai/tool_policy.py`
- Test: `tests/ai/tools/test_registry.py`
- Test: `tests/ai/test_tool_capability_seam.py`
- Test: `tests/ai/test_tool_nudge_policy.py`

- [ ] **Step 1: Write failing tests** asserting the static registry resolves `todo_write`, the main General Agent receives it as an implicit runtime tool, specialist/ChatBI paths do not receive it through the new implicit mount, metadata reports an internal task-state tool with no confirmation, and the model-facing tool inventory contains the trigger guidance.

- [ ] **Step 2: Run the focused registry/capability tests and confirm the missing registration and prompt entries.**

  ```sh
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. pytest -q \
    tests/ai/tools/test_registry.py \
    tests/ai/test_tool_capability_seam.py \
    tests/ai/test_tool_nudge_policy.py
  ```

- [ ] **Step 3: Register the tool and mount it at the existing General-Agent implicit-tool seam.**

  Add the static registry entry and resolve it through the same `RegistryToolProvider` path used by the existing built-in tools. Add one tool description and one routing/nudge row covering multi-step, multi-tool, subagent, dependency, or file-generation work, while explicitly excluding simple single-step queries. Do not add a classifier or change route selection.

  Add neutral metadata with capability `task_planning`, source `platform_control`, side effect `session_state`, confirmation `none`, idempotent `yes`, and explicit nudge mode. Keep the tool out of evidence inference and business confirmation.

- [ ] **Step 4: Run the focused registration and prompt tests.**

  ```sh
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. pytest -q \
    tests/ai/tools/test_registry.py \
    tests/ai/test_tool_capability_seam.py \
    tests/ai/test_tool_nudge_policy.py
  ```

### Task 3a: Prioritize the checklist for structurally multi-step requests

**Files:**
- Modify: `app/services/ai/tool_nudge_policy.py`
- Test: `tests/ai/test_tool_nudge_policy.py`

- [x] Add a structural multi-step detector based on sequence markers, multiple clauses, and action/output connectors; do not classify business intent or add an LLM call.
- [x] When `todo_write` is present, return a forced first-call nudge for multi-step requests before semantic data/knowledge delegation. Preserve explicit sub-agent requests as the higher-priority override.
- [x] Keep single-step data queries on the existing `sub_agent_call` path and limit the behavior in practice to the main General Agent, which is the only runtime path that mounts `todo_write`.
- [x] Tell the model to continue execution after the checklist write; the preflight applies only to the first model call and does not lock subsequent tool calls.

  ```sh
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. pytest -q tests/ai/test_tool_nudge_policy.py
  ```

### Task 4: Fold `todo_update` into the existing process timeline

**Files:**
- Modify: `app/services/ai/runtime/agentscope/process_timeline_snapshot.py`
- Test: `tests/ai/runtime/test_process_timeline_snapshot.py`

- [ ] **Step 1: Write failing reducer tests** for the first `todo_update`, a later full-list replacement, an empty-list clear, malformed event omission, and preservation of existing model/tool/subagent timeline entries.

- [ ] **Step 2: Run the reducer tests and confirm `todo_update` is ignored.**

  ```sh
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. pytest -q tests/ai/runtime/test_process_timeline_snapshot.py
  ```

- [ ] **Step 3: Add one dedicated `kind: "todo"` timeline item.**

  The reducer must replace the existing todo item in place or append one if absent, preserving the latest complete list and counts. An empty list removes the current todo item. Invalid payloads must not corrupt unrelated timeline entries. The persisted item must be JSON-safe and independent of the model conversation history.

- [ ] **Step 4: Run the reducer tests and the existing process timeline tests.**

  ```sh
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. pytest -q tests/ai/runtime/test_process_timeline_snapshot.py
  ```

### Task 5: Render the task checklist in both web surfaces

**Files:**
- Modify: `frontend/src/utils/processTimeline.ts`
- Create: `frontend/src/components/chat/ChatTodoCard.vue`
- Modify: `frontend/src/components/chat/ChatExecutionTimeline.vue`
- Modify: `frontend/src/views/EmbedChat.vue`
- Modify: `frontend/src/views/AgentDebug.vue`
- Test: `frontend/scripts/processTimeline.test.ts`

- [ ] **Step 1: Write failing frontend tests** for the `todo` timeline item type, completed/in-progress/pending rendering semantics, empty-list omission, and history hydration retaining the same item.

- [ ] **Step 2: Run the focused frontend tests and confirm the type and renderer do not support todo items.**

  ```sh
  npm --prefix frontend run test -- --run scripts/processTimeline.test.ts
  ```

- [ ] **Step 3: Extend the shared timeline type and renderer.**

  Add a `ProcessTimelineTodoItem` with the full list and counts. Render a compact `任务清单` card in `ChatTodoCard`, as a sibling of `ChatExecutionTimeline`; use a check mark for `completed`, active marker for `in_progress`, and hollow marker for `pending`. Filter todo items out of the execution card so the checklist is not duplicated. Do not change existing tool, reasoning, narration, or subagent rendering.

- [ ] **Step 4: Run the focused frontend tests.**

  ```sh
  npm --prefix frontend run test -- --run scripts/processTimeline.test.ts
  ```

### Task 6: Verify live SSE, history persistence, and non-regression

**Files:**
- Test: `tests/services/ai/test_agent_service_stream_content.py`
- Test: `tests/ai/test_session_tool_artifact.py`
- Modify: `tests/CHECKLIST.md`
- Modify: `docs/superpowers/specs/2026-08-17-todo-write-tool-design.md` if implementation details differ from the approved design

- [ ] **Step 1: Write failing integration tests** that a queued `todo_update` reaches the AgentService stream and that the final assistant history payload contains the latest todo timeline item without adding a model message or grounding evidence.

- [ ] **Step 2: Run the focused integration tests and confirm the event is not yet propagated or persisted.**

  ```sh
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. pytest -q \
    tests/services/ai/test_agent_service_stream_content.py \
    tests/ai/test_session_tool_artifact.py
  ```

- [ ] **Step 3: Add only the missing stream/history wiring.**

  Preserve the existing `event_queue` merge, `process_timeline` finalization, memory-service message shape, and cancellation behavior. Do not create a new database model or API endpoint. Record the new test coverage in `tests/CHECKLIST.md`.

- [ ] **Step 4: Run the complete focused regression set.**

  ```sh
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. pytest -q \
    tests/ai/tools/test_todo_tools.py \
    tests/ai/tools/test_registry.py \
    tests/ai/test_tool_capability_seam.py \
    tests/ai/test_tool_nudge_policy.py \
    tests/ai/runtime/test_process_timeline_snapshot.py \
    tests/ai/test_agent_service_stream_content.py \
    tests/ai/test_session_tool_artifact.py
  npm --prefix frontend run test -- --run scripts/processTimeline.test.ts
  git diff --check
  ```

  Expected: all focused tests pass and the scoped diff has no whitespace errors.
