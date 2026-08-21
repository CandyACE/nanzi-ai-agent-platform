# Context Compaction Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist platform and AgentScope context-compression events as structured, session-scoped Redis records for seven days and expose them in a ChatLogs “上下文” tab.

**Architecture:** A dedicated Redis LIST stores JSON records under the existing user/conversation key convention. The chat stream records both compression SSE event types at their emission boundary, while a read-only authenticated API returns the session timeline. ChatLogs lazily loads and renders the timeline beside the existing conversation and trace tabs.

**Tech Stack:** FastAPI, Pydantic, async Redis, pytest, Vue 3, TypeScript, Tailwind CSS.

---

### Task 1: Add the Redis context-compaction record service

**Files:**
- Create: `app/services/ai/context_compaction_log_service.py`
- Test: `tests/ai/test_context_compaction_log_service.py`

- [x] Write tests for a session-scoped key, JSON record serialization, list ordering, seven-day expiry, maximum record trimming, and Redis-unavailable fallback.
- [x] Run `PYTHONPATH=. venv/bin/python -m pytest tests/ai/test_context_compaction_log_service.py -q`; confirm it fails because the service does not exist.
- [x] Implement `ContextCompactionLogService` with `append`, `list_records`, `key`, `TTL_SECONDS = 604800`, and `MAX_RECORDS = 500`.
- [x] Use a Redis pipeline for `RPUSH`, `LTRIM`, and `EXPIRE`; decode bytes and ignore malformed records on reads.
- [x] Run the focused service tests and confirm they pass.

### Task 2: Persist both compression event types at the chat stream boundary

**Files:**
- Modify: `app/services/ai/agent_service.py`
- Modify: `app/services/ai/runtime/agentscope/event_stream.py`
- Test: `tests/services/ai/test_context_compaction_event_persistence.py`

- [x] Write tests proving `context_summarized` and `context_compression` become records with event type, source, stage, trace ID, conversation ID, timestamp, and event payload fields.
- [x] Run the focused tests and confirm they fail before the recorder is wired.
- [x] Add a small AgentService recording helper that is best-effort and never interrupts SSE delivery.
- [x] Record platform events at pre-route and final-model emission points; record AgentScope events when they are mapped through the executor stream.
- [x] Keep the existing SSE payload unchanged and preserve seven-day Redis retention.
- [x] Run the focused persistence tests and the existing context-compaction tests.

### Task 3: Add the authenticated context-compaction API

**Files:**
- Modify: `app/api/v1/endpoints/chat.py`
- Modify: `frontend/src/api/agent.ts`
- Test: `tests/api/v1/test_chat_context_compactions.py`

- [x] Write API contract tests for the current user’s conversation, empty results, malformed-record filtering, and prevention of cross-user access.
- [x] Run the focused API tests and confirm they fail before the endpoint exists.
- [x] Add `GET /api/v1/chat/conversation/{conversation_id}/context_compactions` with `require_api_key` and a structured response model.
- [x] Return records in chronological order with count and retention metadata; never expose another user’s Redis key.
- [x] Run the focused API tests.

### Task 4: Add the ChatLogs “上下文” tab

**Files:**
- Modify: `frontend/src/views/ChatLogs.vue`
- Modify: `frontend/src/api/agent.ts`
- Test: `tests/frontend/test_chat_context_compactions_contract.py`

- [x] Write a frontend contract test for the new tab, lazy loading by conversation ID, loading/empty/error states, source/stage labels, metric display, and preview rendering.
- [x] Run the focused contract test and confirm it fails before the UI exists.
- [x] Add a typed API method and a lazy `loadContextCompactions` flow when the selected log or context tab changes.
- [x] Render chronological cards with event type, stage, timestamp, dropped/kept counts, token ratio, and a collapsible preview.
- [x] Run frontend contract tests and `./node_modules/.bin/vue-tsc --noEmit` from `frontend/`.

### Task 5: Final verification

**Files:**
- Verify: all files above

- [x] Run backend focused tests for Redis service, event persistence, API, and existing context compaction behavior.
- [x] Run frontend focused tests for the ChatLogs contract and existing internal-context display behavior.
- [x] Run `git diff --check` and inspect `git status --short`.
- [x] Do not start services, run deployment scripts, stage files, or create a commit.
