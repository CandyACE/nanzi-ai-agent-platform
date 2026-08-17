# `ask_user_question` Implementation Plan

> **For agentic workers:** Implement this plan task-by-task with TDD. Keep unrelated worktree changes intact and do not commit unless explicitly requested.

**Goal:** 让主助手、ChatBI 和知识库助手能够主动向用户提问并在用户回答后继续同一会话。

**Architecture:** `ask_user_question` 使用独立的问题 payload 和 `UserQuestionCard`，只复用已有 HITL 的事件流、历史和新一轮消息机制。服务端以 Redis pending 记录保存问题、选项、归属和 TTL；用户回答经过服务端校验后，以 `【用户回答】` 回执进入上一智能体的新一轮执行。子代理恢复和路由器未选智能体前的澄清不在本期范围内。

**Tech Stack:** Python 3.11+, Pydantic 2, Redis, FastAPI SSE, AgentScope runtime, Vue 3, TypeScript, pytest.

---

### Task 1: Define the question protocol and server validation

**Files:**
- Create: `app/services/ai/user_question.py`
- Create: `app/services/ai/tools/user_question_tools.py`
- Test: `tests/ai/tools/test_user_question_tool.py`

- [x] Write failing tests for argument validation, unique question ID generation, safe JSON output, single/multi-select limits, and rejection of duplicate option IDs.
- [x] Write failing tests for parsing a question payload and building a structured `【用户回答】` receipt without trusting display labels.
- [x] Implement the Pydantic models, tool, payload parser, receipt builder, and fixed-size validation limits.
- [x] Verify the focused tool tests pass.

### Task 2: Add pending question storage and answer validation

**Files:**
- Create: `app/services/ai/user_question_store.py`
- Test: `tests/ai/test_user_question_store.py`

- [x] Write failing tests for pending creation, same-user/same-conversation lookup, TTL expiration, atomic submit, repeated submit idempotency, and cross-user rejection.
- [x] Implement Redis-backed storage with `pending/submitted/expired` status and a bounded TTL; Redis unavailable is fail-closed and does not accept an unverified answer.
- [x] Add server-side validation of `question_id`, selected option IDs, single/multi-select mode, and custom-input permission.
- [x] Verify store tests pass with an explicit process-local test store and no production Redis dependency.

### Task 3: Register the global interaction capability

**Files:**
- Modify: `app/services/ai/tools/registry.py`
- Modify: `app/services/ai/runtime/agentscope/tools.py`
- Modify: `app/services/ai/tool_capability.py`
- Modify: `app/services/ai/tool_policy.py`
- Test: `tests/ai/tools/test_user_question_tool.py`
- Test: `tests/ai/test_tool_capability_seam.py`

- [x] Write failing tests that `ask_user_question` appears in implicit tool resolution and that Prompt/runtime visibility agree.
- [x] Register the tool as an interaction capability that bypasses ordinary approval while remaining distinct from business writes and ordinary read tools.
- [x] Keep configured tool filtering and unrelated capability grants unchanged; the interaction tool follows the existing implicit-tool resolution path.
- [x] Verify focused capability and permission tests pass.

### Task 4: Pause the execution loop and emit the SSE event

**Files:**
- Modify: `app/services/ai/runners/assistant_agent_runner.py`
- Modify: `app/services/ai/runners/chatbi/react_stream.py`
- Modify: `app/services/ai/runners/chatbi/agent_builder.py` only if runtime assembly requires it
- Modify: `app/services/ai/runners/knowledge_agent_runner.py` only if its stream path differs
- Test: `tests/ai/runners/test_user_question_pause.py`

- [x] Write failing tests that an `awaiting_user` question is an execution interrupt and the turn is marked pending.
- [x] Add one shared payload builder and call it from the existing tool-result handling paths instead of duplicating parsing rules per runner.
- [x] Ensure the parent trace records the pending question and the current execution terminates cleanly without normal synthesis.
- [x] Verify assistant, ChatBI, and knowledge paths share the focused pause implementation.

### Task 5: Continue the same agent after a validated answer

**Files:**
- Modify: `app/api/v1/endpoints/chat.py` or the existing chat request decision entry point
- Modify: `app/services/ai/router_service.py`
- Modify: `app/services/ai/agent_service.py` only where the answer receipt enters the next turn
- Test: `tests/services/ai/test_router_service.py`
- Test: `tests/ai/test_user_question_continuation.py`

- [x] Write failing tests that a valid receipt stays on the previous agent and an invalid/expired receipt does not reach the model.
- [x] Add a question-receipt classifier with explicit `question_id` and server-validated answer data; preserve the raw custom input as user content after validation.
- [x] Reuse the current conversation ID and continue through an ordinary new turn; do not restore the original generator.
- [x] Add protection against repeated questions in the same conversation and verify continuation tests pass.
- [x] Add a cancellation receipt that atomically closes the pending question and stops the next turn before routing, model, or tool execution.

### Task 6: Add the frontend question card and SSE handling

**Files:**
- Create: `frontend/src/utils/userQuestion.ts`
- Create: `frontend/src/components/UserQuestionCard.vue`
- Modify: `frontend/src/utils/agentscopeSseHandlers.ts`
- Modify: `frontend/src/views/EmbedChat.vue`
- Modify: `frontend/src/views/AgentDebug.vue`
- Test: `tests/frontend/test_user_question_contract.py`

- [x] Write failing contract tests for parsing `user_question`, rendering independent question-card fields, selected option serialization, and pending/submitted/stale states.
- [x] Implement the card with separate single-select, multi-select, and custom-input behavior; submit only option IDs plus custom input.
- [x] Wire the card into both pages without reusing `BusinessConfirmationCard.vue`; after submission send the receipt through the ordinary chat continuation path.
- [x] Add a separate “取消提问” action; cancelled cards become read-only and send a structured cancellation receipt.
- [x] Verify frontend contracts and existing business-confirmation contracts pass.

### Task 7: Persist snapshots, documentation, and regression verification

**Files:**
- Modify: `app/services/ai/agent_prompts.py`
- Modify: `tests/CHECKLIST.md`
- Modify: `docs/superpowers/specs/2026-08-17-ask-user-question-design.md`
- Modify: `docs/superpowers/plans/2026-08-17-ask-user-question-plan.md`

- [x] Write failing prompt tests for when to ask, when to infer, one-question-per-turn, and no-repeat-after-answer guidance.
- [x] Add the prompt section and document that routing-before-agent-selection and subagent resume are later phases.
- [x] Add the question event to the process-timeline snapshot path; the answer remains an ordinary conversation user message.
- [x] Run focused backend/frontend tests, Python compilation, frontend contract checks, and `git diff --check`; record pre-existing baseline failures separately.
