# AI 聊天发送防重与断线恢复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 EmbedChat 与 AgentDebug 的一次发送意图在前端、断线恢复和服务端重试路径中都只产生一次可识别的会话任务。

**Architecture:** 前端把“正在提交”和“正在生成”拆成两个状态，所有发送入口先经过同一个同步提交门禁并冻结参数快照。服务端用 Redis 保存 `client_request_id` 的短期幂等状态，同时复用会话运行锁提供运行中状态查询；页面加载/切回前台先同步运行状态，再决定是否允许发送。相同文本不默认去重，只有同一个客户端请求 ID 才视为网络重试。

**Tech Stack:** Vue 3 + TypeScript + FastAPI + Pydantic 2 + SQLAlchemy 2.x async + Redis + pytest。

---

### Task 1: 建立前端发送门禁和不可变发送快照

**Files:**
- Create: `frontend/src/composables/chat/useChatSendGate.ts`
- Modify: `frontend/src/views/EmbedChat.vue`
- Modify: `frontend/src/views/AgentDebug.vue`
- Modify: `frontend/src/components/embed/ChatInput.vue`
- Test: `tests/frontend/test_chat_send_gate_behavior.py`
- Test: `tests/frontend/test_chat_send_dedup_contract.py`

- [ ] **Step 1: Write the failing behavior test**

  Export a small `createChatSendGate` from the new composable and test that the first caller owns the gate synchronously, concurrent callers are rejected before their task runs, and the gate is released after success, exception, and early return. Use the existing TypeScript subprocess helper pattern from `tests/frontend/test_chat_shared_helpers_behavior.py`.

  The test must assert these cases:

  ```typescript
  const gate = api.createChatSendGate();
  const first = gate.runExclusive(async () => { await hold.promise; return 'first'; });
  const second = await gate.runExclusive(async () => 'second');
  // second is undefined and its callback was never entered
  hold.resolve();
  await first;
  // a later call succeeds
  ```

- [ ] **Step 2: Run the behavior test and verify RED**

  Run:

  ```bash
  venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_chat_send_gate_behavior.py -q
  ```

  Expected: collection or assertion failure because `useChatSendGate.ts` and `createChatSendGate` do not exist yet.

- [ ] **Step 3: Implement the minimal gate**

  Add a Vue `ref<boolean>` lock and a `runExclusive<T>(task)` function. Set the lock before invoking the task, return `undefined` when already locked, and clear it in `finally`. Keep the gate independent of `isProcessing` so a preflight submission cannot expose a fake cancel action.

- [ ] **Step 4: Refactor both pages to claim before every async preflight**

  Replace the page-local wrapper with the composable gate and change the internal sender to accept an immutable snapshot containing at least `content`, `files`, `clientRequestId`, and the optional grounding action. The normal input path calls the gate before reading mutable state; quick questions, code analysis, edit/resend, regenerate, and grounding actions call the same gate before `nextTick`, `handleSystemCommand`, or history truncation. The internal function must never reread `userInput` after an `await`.

- [ ] **Step 5: Split ChatInput states**

  Add an optional `isSubmitting` prop. Use `isProcessing` only for an active generation and `isSubmitting || isProcessing` for input/menu disabling. During `isSubmitting`, show “准备发送…” and disable the button without emitting `stop`; emit `stop` only while `isProcessing` is true. Pass `sendLocked` and `isProcessing` separately from both pages.

- [ ] **Step 6: Run the behavior and contract tests**

  Run:

  ```bash
  venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_chat_send_gate_behavior.py tests/frontend/test_chat_send_dedup_contract.py -q
  ```

  Expected: all tests pass, including direct send, shortcut, edit/resend, regenerate, and early-unlock contracts.

### Task 2: Add function-level guards for continuation actions

**Files:**
- Modify: `frontend/src/views/EmbedChat.vue`
- Modify: `frontend/src/views/AgentDebug.vue`
- Test: `tests/frontend/test_chat_continuation_dedup_contract.py`

- [ ] **Step 1: Write the failing contract test**

  Assert both pages check `pending.isSubmitting` before starting permission confirmation or external execution resume, set it before the first `await`, and keep the existing button `disabled` bindings. Also assert business-confirmation and user-question submissions remain status-gated.

- [ ] **Step 2: Run the contract test and verify RED**

  Run:

  ```bash
  venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_chat_continuation_dedup_contract.py -q
  ```

  Expected: failure because the current functions only check `status === "pending"` and do not reject an already submitting continuation at the function boundary.

- [ ] **Step 3: Implement the guards**

  Change both `submitPendingExternalExecution` and `confirmPendingPermission` to return when `pending.isSubmitting` is already true, then set the flag synchronously before network work. Do not route these continuation endpoints through the normal text-send lock because they resume an existing AgentScope run and have separate lifecycle state.

- [ ] **Step 4: Run focused continuation tests**

  Run the contract test again and confirm it passes without changing the continuation payloads or permission semantics.

### Task 3: Expose Redis-backed conversation run status

**Files:**
- Modify: `app/services/ai/runtime/session_run_lane.py`
- Modify: `app/api/v1/endpoints/chat.py`
- Test: `tests/ai/runtime/test_session_run_lane.py`
- Test: `tests/api/v1/test_chat_run_status.py`

- [ ] **Step 1: Extend the fake Redis and write failing status tests**

  Add `get` and `ttl` behavior to the test fake, then add tests for an unlocked conversation, a locked conversation returning its trace token and TTL, disabled locking, and unavailable Redis. The status result must not expose arbitrary Redis values beyond the server-generated trace identifier.

- [ ] **Step 2: Run the status tests and verify RED**

  Run:

  ```bash
  venv/bin/python -m pytest -q tests/ai/runtime/test_session_run_lane.py tests/api/v1/test_chat_run_status.py
  ```

  Expected: the existing `is_locked` test is repaired by the fake methods, while the new status API assertions fail because no status method/route exists.

- [ ] **Step 3: Implement a lane status method**

  Add `get_status(user_id, conversation_id)` that returns `{active, trace_id, ttl_seconds}`. Preserve the existing disabled/no-Redis behavior as `active: false`; use the same sanitized lock key and Redis reads as `acquire`.

- [ ] **Step 4: Implement the authenticated status endpoint**

  Add `GET /api/v1/chat/conversation/{conversation_id}/run-status`, authenticate with `require_api_key`, bind the lookup to `_require_chat_user_id`, and return a typed standard response. Do not query or mutate the database.

- [ ] **Step 5: Run backend status tests**

  Run the focused runtime and API tests and confirm they pass. No service startup or real Redis/database access is allowed.

### Task 4: Restore run state on mount and visibility changes

**Files:**
- Create: `frontend/src/composables/chat/useConversationRunStatus.ts`
- Modify: `frontend/src/views/EmbedChat.vue`
- Modify: `frontend/src/views/AgentDebug.vue`
- Test: `tests/frontend/test_conversation_run_status_contract.py`

- [ ] **Step 1: Write the failing composable behavior test**

  Test that refresh results are sequence-safe, an active run sets `remoteRunActive`, inactive results clear it, and a stale response from an older conversation cannot overwrite the current conversation state. Test that polling stops on unmount/cleanup.

- [ ] **Step 2: Run the test and verify RED**

  Run:

  ```bash
  venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_conversation_run_status_contract.py -q
  ```

  Expected: failure because the composable does not exist.

- [ ] **Step 3: Implement the composable**

  Implement `refresh(conversationId, headers)`, `startPolling`, `stopPolling`, and `remoteRunActive`. Use a monotonically increasing request sequence, a bounded 1.5-second poll while active, and no mutation of the page’s local `isProcessing` flag.

- [ ] **Step 4: Integrate both pages**

  Refresh status after the conversation ID is restored/generated and on `visibilitychange` to visible. Include `remoteRunActive` in the send gate precondition and ChatInput busy presentation. Keep explicit Stop available when the remote run is active, and after stopping force a status refresh before allowing a new turn.

- [ ] **Step 5: Handle the existing background producer contract**

  When the SSE fetch ends because the page is hidden/disconnected, keep the page in `remoteRunActive` until the status endpoint reports inactive. Do not remove the backend producer continuation behavior; only prevent an unverified local resend from starting.

- [ ] **Step 6: Run frontend status contracts**

  Run the composable and page integration contract tests. Confirm no `./dev.sh`, browser server, or production service is started.

### Task 5: Add client request idempotency for chat completions

**Files:**
- Create: `app/services/ai/runtime/chat_request_idempotency.py`
- Modify: `app/api/v1/endpoints/chat.py`
- Modify: `frontend/src/views/EmbedChat.vue`
- Modify: `frontend/src/views/AgentDebug.vue`
- Test: `tests/ai/runtime/test_chat_request_idempotency.py`
- Test: `tests/api/v1/test_chat_completions.py`
- Test: `tests/frontend/test_chat_request_idempotency_contract.py`

- [ ] **Step 1: Write failing idempotency unit tests**

  Test a first claim, a concurrent duplicate claim, completion persistence, a failed claim when Redis is unavailable, user/conversation isolation, and expiration/TTL configuration. Use a fake Redis implementing `set(nx=True)`, `get`, and `expire` without connecting to real infrastructure.

- [ ] **Step 2: Run the unit tests and verify RED**

  Run:

  ```bash
  venv/bin/python -m pytest --confcutdir=tests/ai tests/ai/runtime/test_chat_request_idempotency.py -q
  ```

  Expected: failure because the idempotency module and claim methods do not exist.

- [ ] **Step 3: Implement the Redis idempotency store**

  Hash the user, conversation, and client request ID into a Redis key. Store only a bounded JSON status such as `processing/completed/failed`, the generated trace ID when available, and a short expiration. A duplicate must return the existing record and must never execute the model again. Redis unavailability must fail open to the existing run-lane behavior and be observable in logs.

- [ ] **Step 4: Add the request field and endpoint integration**

  Add optional `client_request_id` to `ChatCompletionRequest` with a bounded length. For streaming and non-streaming requests, claim before invoking `agent_service`; stream a structured duplicate event/error with the prior trace ID instead of creating another producer. Mark the claim completed or failed from the producer/standard response lifecycle.

- [ ] **Step 5: Add frontend request IDs**

  Generate one UUID/fallback ID per accepted send snapshot and include it in the completion body. A retry of the same snapshot must reuse the ID; a new user intent must generate a new one. Add contracts for both pages and assert the ID is generated before async preflight.

- [ ] **Step 6: Add API regression tests**

  Add tests proving duplicate IDs do not invoke `agent_service.chat_completion_stream` twice, different IDs still create distinct requests, and duplicate responses preserve the original trace ID. Keep tests isolated from MySQL/Redis fixtures where possible.

### Task 6: Final verification and review

**Files:**
- Modify: `tests/CHECKLIST.md` only if the repository convention requires a new entry for this completed change

- [ ] **Step 1: Run focused frontend tests**

  ```bash
  venv/bin/python -m pytest --confcutdir=tests/frontend \
    tests/frontend/test_chat_send_gate_behavior.py \
    tests/frontend/test_chat_send_dedup_contract.py \
    tests/frontend/test_chat_continuation_dedup_contract.py \
    tests/frontend/test_conversation_run_status_contract.py \
    tests/frontend/test_chat_request_idempotency_contract.py -q
  ```

- [ ] **Step 2: Run focused backend tests**

  ```bash
  venv/bin/python -m pytest --confcutdir=tests/ai \
    tests/ai/runtime/test_session_run_lane.py \
    tests/ai/runtime/test_chat_request_idempotency.py \
    tests/api/v1/test_chat_run_status.py \
    tests/api/v1/test_chat_completions.py -q
  ```

  Report infrastructure/fixture failures separately from implementation failures.

- [ ] **Step 3: Run static checks without starting services**

  ```bash
  frontend/node_modules/.bin/vue-tsc --noEmit
  venv/bin/python -m compileall -q app/services/ai/runtime app/api/v1/endpoints/chat.py
  git diff --check -- frontend/src app/services/ai/runtime app/api/v1/endpoints/chat.py tests
  ```

- [ ] **Step 4: Review the final diff**

  Confirm no unrelated existing edits were overwritten, no database migration or runtime configuration was changed, and no `./dev.sh`/deployment command was run.

- [ ] **Step 5: Request code review**

  Dispatch a reviewer against the final uncommitted diff and address critical/important findings. Do not stage, commit, push, or create a PR unless the user explicitly asks.
