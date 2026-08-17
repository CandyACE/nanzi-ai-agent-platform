# 一次性子代理委派协议增强 Implementation Plan

> **For agentic workers:** Implement this plan task-by-task with TDD. Do not introduce durable child sessions or background continuation in this change.

**Goal:** Strengthen the existing one-shot `sub_agent_call` with run identity, parent/child trace metadata, cancellation, per-call depth limits, tool filtering, optional structured output, and explicit stop reasons while preserving the two-argument call.

**Architecture:** Keep `AgentDelegateTool` as the current execution boundary and extend `SubAgentRequest`/`SubAgentResult` as the typed protocol. Resolve a request-scoped child tool set before dispatch, pass only that set into the child executor, and attach lifecycle metadata to the existing shared trace buffer rather than creating a new persistence model.

**Tech Stack:** Python 3.11+, Pydantic 2, pytest, current AgentScope runtime, existing `AgentContext`, `AgentDispatcher`, and `AgentExecutionStep.meta_info`.

---

### Task 1: Extend the typed request/result protocol

**Files:**
- Modify: `app/services/ai/subagent_protocol.py`
- Test: `tests/ai/test_subagent_contract.py`

- [x] **Step 1: Write failing tests** for `run_id`, parent/child trace fields, `max_depth`, `tool_filter`, `output_schema`, explicit `stop_reason`, and JSON-safe metadata that never includes credentials or raw query text.
- [x] **Step 2: Run the focused contract tests.**

  ```sh
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. pytest -q tests/ai/test_subagent_contract.py
  ```

  Expected: FAIL because the new fields and stop-reason values do not exist.
- [x] **Step 3: Implement the minimum protocol fields.** Preserve `to_tool_text()` and existing `SubAgentResultStatus` compatibility. Add a typed stop-reason enum or literal, structured result storage, and metadata serialization that reports counts/lengths rather than raw content.
- [x] **Step 4: Re-run the focused contract tests.** Expected: PASS.

### Task 2: Add request validation and depth/tool-filter helpers

**Files:**
- Modify: `app/services/ai/tools/agent_delegate_tool.py`
- Test: `tests/ai/test_sub_agent_delegation.py`

- [x] **Step 1: Write failing tests** for default depth behavior, `max_depth` below/equal/above the current depth, unknown filter names, and filters that narrow but never widen target tools.
- [x] **Step 2: Run the focused delegation tests and confirm the new cases fail.**
- [x] **Step 3: Implement pure helpers** that normalize optional filter lists, intersect them with the target configuration, reject unknown names, and enforce the existing platform maximum. Return typed failure reasons instead of raising generic exceptions for expected policy rejection.
- [x] **Step 4: Run the new tests and the existing depth/self-delegation tests.** Expected: PASS.

### Task 3: Add optional model-tool parameters without breaking existing calls

**Files:**
- Modify: `app/services/ai/tools/agent_delegate_tool.py`
- Modify: `app/services/ai/tools/tool_compat.py` only if signature-schema generation cannot represent the optional JSON fields
- Test: `tests/ai/test_sub_agent_delegation.py`

- [x] **Step 1: Write a failing schema test** that the registered `sub_agent_call` accepts the original `agent_name/query` pair and exposes optional `max_depth`, `tool_filter`, and `output_schema` fields.
- [x] **Step 2: Run the schema test and confirm the current FunctionTool schema lacks the fields.**
- [x] **Step 3: Add optional arguments with safe defaults.** Keep the callable return type text-compatible. Validate the optional values at the delegation boundary, not in the Prompt.
- [x] **Step 4: Run schema and existing invocation tests.** Expected: PASS.

### Task 4: Thread run identity and parent/child metadata through execution

**Files:**
- Modify: `app/services/ai/tools/agent_delegate_tool.py`
- Modify: `app/core/context.py` only for request-scoped child identifiers needed by runtime tools
- Test: `tests/ai/test_sub_agent_delegation.py`

- [x] **Step 1: Write failing tests** asserting every successful, timeout, interruption, and exception result has a `run_id`, parent trace attribution, and a distinct child trace id.
- [x] **Step 2: Run those tests and verify the current result/trace objects do not contain the associations.**
- [x] **Step 3: Generate one run id per accepted delegation and pass it to the child dispatch context.** Keep the existing shared trace buffer and event queue, but attach a `subagent` metadata object to the child execution steps and completion result.
- [x] **Step 4: Run all existing delegation tests.** Expected: PASS without changing the current log forwarding behavior.

### Task 5: Apply the filtered tool set to child execution

**Files:**
- Modify: `app/services/ai/tools/agent_delegate_tool.py`
- Modify: `app/services/ai/dispatcher.py` or the target Executor construction path only where a request-scoped tool override is currently absent
- Test: `tests/ai/test_sub_agent_delegation.py`

- [x] **Step 1: Write failing tests** that a child with `tool_filter=["search_knowledge_base"]` receives only that tool, a filter cannot add `Bash`, and an unknown tool is rejected before dispatch.
- [x] **Step 2: Run the tests and confirm target configuration currently controls the complete tool set.**
- [x] **Step 3: Pass an explicit child tool allowlist through the existing dispatch context.** Intersect with target Agent configuration and use the same list for Prompt assembly and Runtime Tool construction. Do not mutate the published target configuration.
- [x] **Step 4: Run focused Assistant/Knowledge tool-resolution tests plus delegation tests.** Expected: PASS.

### Task 6: Add cancellation and explicit stop reasons

**Files:**
- Modify: `app/services/ai/tools/agent_delegate_tool.py`
- Modify: `app/services/ai/subagent_protocol.py`
- Test: `tests/ai/test_sub_agent_delegation.py`
- Test: `tests/ai/runtime/test_conversation_run_cancel.py` only if the current cancellation hook is the correct integration point

- [x] **Step 1: Write failing tests** for timeout, caller cancellation, permission interruption, depth rejection, invalid output, and ordinary execution failure. Each must assert the distinct stop reason and that the child stream is closed.
- [x] **Step 2: Run the focused tests and observe the missing cancellation/stop-reason behavior.**
- [x] **Step 3: Use the current run cancellation mechanism where available and map each terminal path explicitly.** Timeout must close the async generator; cancellation must not be reported as successful partial content; permission and external execution interruptions must preserve their existing user-facing guidance while carrying the typed reason.
- [x] **Step 4: Run all delegation and cancellation tests.** Expected: PASS.

### Task 7: Add optional structured output validation

**Files:**
- Modify: `app/services/ai/tools/agent_delegate_tool.py`
- Modify: `app/services/ai/subagent_protocol.py`
- Test: `tests/ai/test_sub_agent_delegation.py`
- Test: `tests/ai/test_subagent_contract.py`

- [x] **Step 1: Write failing tests** for a valid object schema, invalid schema, valid structured child result, and schema mismatch. Existing text-only children must continue to work.
- [x] **Step 2: Run the tests and confirm no structured-output path exists.**
- [x] **Step 3: Add a narrow object-schema validator using the repository's existing validation dependencies.** Accept only JSON-safe object results; on mismatch return `invalid_output` and do not label the run completed. Keep `structured` separate from compatibility text.
- [x] **Step 4: Run contract and delegation tests.** Expected: PASS.

### Task 8: Documentation and focused verification

**Files:**
- Modify: `docs/superpowers/specs/2026-08-17-subagent-delegation-protocol-design.md`
- Modify: `docs/superpowers/plans/2026-08-17-subagent-delegation-protocol.md`
- Modify: `tests/CHECKLIST.md` only if the existing delegation checklist needs the new contract recorded

- [x] **Step 1: Update the design and plan with exact implemented behavior and known non-goals.**
- [x] **Step 2: Run the focused suite.**

  ```sh
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. pytest -q \
    tests/ai/test_subagent_contract.py \
    tests/ai/test_sub_agent_delegation.py \
    tests/ai/test_tool_runtime_config.py \
    tests/ai/runtime/test_conversation_run_cancel.py \
    tests/ai/runtime/test_agentscope_tooling.py
  ```

- [x] **Step 3: Run syntax and hygiene checks.**

  ```sh
  PYTHONDONTWRITEBYTECODE=1 python -m compileall -q app tests/ai
  git diff --check
  ```

- [x] **Step 4: Report any unrelated baseline failures separately.** Do not claim independent child-session persistence or full dsh parity.

### Task 9: Add live and trace UI observability

**Files:**
- Modify: `app/api/v1/endpoints/chat.py`
- Modify: `app/services/ai/tools/agent_delegate_tool.py`
- Add: `frontend/src/utils/subagentTrace.ts`
- Modify: `frontend/src/utils/processTimeline.ts`
- Modify: `frontend/src/utils/agentscopeSseHandlers.ts`
- Modify: `frontend/src/components/chat/ChatExecutionTimeline.vue`
- Modify: `frontend/src/components/TraceLogViewer.vue`
- Modify: `frontend/src/views/ChatLogs.vue`
- Modify: `frontend/src/views/EmbedChat.vue`
- Modify: `frontend/src/views/AgentDebug.vue`
- Modify: `frontend/src/utils/chatSessionExport.ts`
- Test: `tests/ai/test_sub_agent_delegation.py`
- Test: `frontend/scripts/subagentTrace.test.ts`

- [x] **Step 1: Write failing coverage** for forwarding `subagent` metadata to live log events and normalizing the shared frontend metadata representation.
- [x] **Step 2: Add a lifecycle log** so every accepted delegation has a visible pending and terminal node in the AI thinking card; forwarded child logs carry the same metadata.
- [x] **Step 3: Expose persisted `meta_info`, `span_id`, and `parent_span_id` from the chat trace endpoint.** Keep full lineage fields in trace detail and export only a compact summary.
- [x] **Step 4: Run backend delegation tests and frontend utility/export smoke tests.** Existing pages without subagent metadata remain unchanged.

## Verification record

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. pytest -q tests/ai/test_subagent_contract.py tests/ai/test_sub_agent_delegation.py tests/ai/runtime/test_agentscope_tooling.py tests/ai/runtime/test_conversation_run_cancel.py -o cache_dir=/tmp/nanzi-pytest-cache` — 70 passed.
- `cd frontend && ./node_modules/.bin/sucrase-node scripts/subagentTrace.test.ts && ./node_modules/.bin/sucrase-node scripts/chatSessionExport.test.ts` — both passed.
- `PYTHONPYCACHEPREFIX=/tmp/nanzi-pycache-ui PYTHONDONTWRITEBYTECODE=1 /Users/chenxiaolong/.local/bin/python3.11 -m py_compile app/api/v1/endpoints/chat.py app/services/ai/tools/agent_delegate_tool.py` — passed.
- `git diff --check` — passed.
- `vue-tsc -b` remains blocked by pre-existing frontend type errors and the sandbox cannot create `frontend/node_modules/.tmp`; no new errors were reported for the added subagent utility or timeline/trace templates before the existing baseline diagnostics.
- The combined command that also included `tests/ai/test_tool_runtime_config.py` reached the repository database fixture and reported six setup errors because MySQL was unavailable at `localhost:3306`; this is an environment prerequisite failure, not an assertion failure from this change.
- The implementation does not add durable child-session persistence, background continuation, or a cold-resume protocol.
