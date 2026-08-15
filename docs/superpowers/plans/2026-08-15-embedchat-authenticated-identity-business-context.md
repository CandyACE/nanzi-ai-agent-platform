# EmbedChat Authenticated Identity and Business Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use test-driven-development and complete each task in order.

**Goal:** Remove host-controlled identity injection from EmbedChat and establish `business_context` as the only mutable host context while keeping authenticated user identity server-owned.

**Architecture:** The frontend treats server-authenticated `currentUser` as read-only. Host messages merge only sanitized business context into a nested `injected_context.business_context`. The API endpoint and AgentService sanitize client-provided injected context again before runtime prompt assembly.

**Tech Stack:** Vue 3 + TypeScript, FastAPI + Pydantic, AgentService prompt assembly, pytest contract/unit tests.

---

## Task 1: Add failing frontend and backend identity-boundary tests

**Files:**
- Create: `tests/frontend/test_embed_authenticated_identity_contract.py`
- Create: `tests/ai/test_business_context_sanitization.py`
- Reference: `frontend/src/views/EmbedChat.vue`, `frontend/src/views/Chat.vue`, `app/api/v1/endpoints/chat.py`, `app/services/ai/agent_service.py`

1. Assert `INIT_CONFIG.user_info` is absent from Chat and EmbedChat.
2. Assert host context uses `business_context` and cannot assign `currentUser`.
3. Add a unit test for filtering identity-shaped keys from client business context.
4. Assert API and AgentService use the sanitization boundary before prompt injection.
5. Run the focused tests and confirm RED.

## Task 2: Implement frontend protocol and state separation

**Files:**
- Modify: `frontend/src/views/Chat.vue`
- Modify: `frontend/src/views/EmbedChat.vue`
- Modify: `frontend/src/views/WidgetDebugger.vue`

1. Remove the mainline `INIT_CONFIG.user_info` payload.
2. Remove `currentUser` writes from `INIT_CONFIG`, `SYNC_STATE`, and `UPDATE_CONTEXT`.
3. Add business-context merge logic with reserved identity-key filtering.
4. Send nested `injected_context.business_context` while preserving device hints.
5. Update generated integration examples to use `business_context`.

## Task 3: Enforce the boundary on the backend

**Files:**
- Create: `app/services/ai/business_context.py`
- Modify: `app/api/v1/endpoints/chat.py`
- Modify: `app/services/ai/agent_service.py`

1. Add a shared sanitizer for client injected context and reserved authenticated identity keys.
2. Sanitize request debug options before storing request context or calling AgentService.
3. Sanitize again at prompt assembly and render nested business context with an explicit prefix.
4. Keep AgentService `user_info` sourced from `require_api_key` as the only authenticated identity input.

## Task 4: Verify identity isolation and regressions

**Files:**
- Verify: `tests/frontend/test_embed_authenticated_identity_contract.py`
- Verify: `tests/ai/test_business_context_sanitization.py`
- Verify: related EmbedChat/WidgetDebugger contracts

1. Run focused tests and related frontend contracts.
2. Run `vue-tsc --noEmit` and `git diff --check`.
3. Inspect the diff for any remaining `INIT_CONFIG.user_info` protocol use.

No commit, staging, service startup, or database change is part of this plan.
