# 输入框上下文压缩次数与时序弹框 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 EmbedChat 和 AgentDebug 输入框点击上下文使用浮标展开的卡片中显示当前会话压缩次数，并用共享时序组件打开与 ChatLogs 一致的压缩记录弹框。

**Architecture:** 新增 `useContextCompactions` 负责按会话读取已有压缩记录接口、headers 传递和请求竞态保护；新增 `ContextCompactionTimeline.vue` 统一 ChatLogs 与 ChatInput 的记录展示；父页面持有会话和鉴权上下文，ChatInput 只负责入口和弹框 UI。

**Tech Stack:** Vue 3 Composition API, TypeScript, Axios, Tailwind CSS, pytest frontend contract tests, vue-tsc.

---

### Task 1: Add the shared context-compactions composable

**Files:**
- Create: `frontend/src/composables/useContextCompactions.ts`
- Test: `tests/frontend/test_context_compactions_composable_contract.py`

- [x] Write failing contract tests that cover the composable's current conversation, empty conversation, custom headers, empty result, request error, and stale response contract.
- [x] Run the focused composable contract test and confirm failure because the composable did not exist.
- [x] Implement `useContextCompactions` with `ContextCompactionRecord` imports, `latestRequestId`, `refreshContextCompactions(force = false)`, and `contextCompactionCount` computed from both event types returned by the API.
- [x] Keep failed reads isolated to compaction state; clear state when `conversationId` is empty and ignore responses whose request ID is stale.
- [x] Run the composable contract tests and confirm they pass.

### Task 2: Extract the shared context-compaction timeline

**Files:**
- Create: `frontend/src/components/chat/ContextCompactionTimeline.vue`
- Modify: `frontend/src/views/ChatLogs.vue`
- Test: `tests/frontend/test_context_compaction_timeline_contract.py`

- [x] Write a failing static contract test requiring the shared component to render event type/source/stage/time, dropped/kept, token/summary metrics, preview, loading, empty, error and retry states, and requiring ChatLogs to import/use it.
- [x] Run the focused contract test and confirm failure before the component existed.
- [x] Move the existing ChatLogs timeline card formatting into `ContextCompactionTimeline.vue` with typed props and a refresh event; keep preview as text interpolation, not `v-html`.
- [x] Replace the inline ChatLogs context panel with the shared component and pass its existing records/loading/error state.
- [x] Run the component contract test and existing ChatLogs/frontend contracts.

### Task 3: Add the ChatInput compression count and modal

**Files:**
- Modify: `frontend/src/components/embed/ChatInput.vue`
- Test: `tests/frontend/test_chat_input_context_compaction_contract.py`

- [x] Write a failing static contract test for the `context-compaction-count`/records props, the clickable “压缩 N 次” entry, modal open/close semantics, and the shared timeline component usage.
- [x] Run the focused contract test and confirm failure before the input UI existed.
- [x] Add optional typed props for compaction records/count/loading/error and a callback/event for refresh; render the count entry inside the expanded context usage card only when a conversation ID is available from the parent-provided state.
- [x] Add a positioned modal above the input with close and refresh controls, preserve the existing context usage details popup, and prevent the modal from blocking send/stop controls.
- [x] Run the ChatInput contract and `vue-tsc --noEmit` from `frontend/`.

### Task 4: Wire EmbedChat and AgentDebug data flow

**Files:**
- Modify: `frontend/src/views/EmbedChat.vue`
- Modify: `frontend/src/views/AgentDebug.vue`
- Modify: `frontend/src/composables/useContextCompactions.ts`
- Test: `tests/frontend/test_context_compaction_input_integration_contract.py`

- [x] Write a failing integration contract test requiring both parent views to call the composable, pass the current records/count/loading/error into ChatInput, pass EmbedChat auth headers, and refresh after a completed send.
- [x] Run the focused integration test and confirm failure before parent wiring existed.
- [x] Add the composable to both parent views using their current `conversationId`; use `embedAuthHeaders()` for EmbedChat and API-key headers for AgentDebug.
- [x] Refresh compaction records on conversation/model changes and after the existing send completion path; do not change message payloads or SSE rendering.
- [x] Run the integration contract and existing context usage/input tests.

### Task 5: Final verification

**Files:**
- Verify: all files above

- [x] Run all new frontend contract tests plus the existing context usage, ChatInput, ChatLogs and internal-context tests.
- [x] Run `./node_modules/.bin/vue-tsc --noEmit` from `frontend/`.
- [x] Run `git diff --check` and inspect `git status --short`, including the already-existing unrelated changes and new spec/plan files.
- [x] Do not run `./dev.sh`, deployment scripts, stage files, or create a commit.
