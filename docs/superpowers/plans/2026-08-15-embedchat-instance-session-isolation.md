# EmbedChat Instance Session Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use test-driven-development and complete each task in order.

**Goal:** Make EmbedChat sessions isolated per `instance_id` while preserving the existing legacy and mainline conversation behavior.

**Architecture:** Keep a dual-track session policy inside `EmbedChat.vue`. Legacy callers continue to use the fixed localStorage key and user-level server active-conversation endpoint; callers with `instance_id` use an encoded instance-specific localStorage key and an instance-scoped server active-conversation endpoint. Explicit `conversation_id` remains authoritative in both tracks.

**Tech Stack:** Vue 3 + TypeScript, browser localStorage, FastAPI conversation APIs, pytest source-contract tests.

---

## Task 1: Add failing session-isolation contract tests

**Files:**
- Create: `tests/frontend/test_embed_instance_session_contract.py`
- Reference: `frontend/src/views/EmbedChat.vue`

1. Add source-contract assertions for the legacy key, instance-scoped key helper, instance identity parsing, and the legacy-only active API branch.
2. Assert that conversation restoration is performed after instance identity resolution rather than by the pre-auth mount path.
3. Run the focused test file and confirm it fails against the current implementation.

## Task 2: Implement dual-track conversation storage and identity resolution

**Files:**
- Modify: `frontend/src/views/EmbedChat.vue`

1. Add constants and helpers for normalizing `instance_id`, selecting the storage key, reading persisted conversation IDs, and persisting IDs.
2. Resolve `instance_id` from the URL before any conversation initialization.
3. Apply `instance_id` from `INIT_CONFIG` before handling its explicit conversation or agent selection.
4. Remove the eager mount-time legacy conversation restore; let authenticated `initChat` perform the ordered restore.

## Task 3: Route all conversation persistence through the selected policy

**Files:**
- Modify: `frontend/src/views/EmbedChat.vue`

1. Replace direct legacy-key writes in new-session creation, history selection, explicit initialization, and active-conversation restoration with the selected storage helper.
2. Pass `instance_id` to `/api/v1/chat/active` so isolated instances can recover the same conversation across machines without sharing pointers with other instances.
3. Preserve legacy fallback order: explicit conversation ID, persisted legacy ID, server active conversation, then new conversation.
4. Preserve isolated fallback order: explicit conversation ID, instance-scoped local ID, instance-scoped server active ID, then new conversation.

## Task 4: Verify focused behavior and regressions

**Files:**
- Verify: `tests/frontend/test_embed_instance_session_contract.py`
- Verify: `tests/frontend/test_portal_notification_bell_contract.py`
- Verify: `tests/frontend/test_embed_url_agent_lock_contract.py`
- Verify: `tests/frontend/test_widget_debugger_integration_guide.py`

1. Run the new contract tests and the related existing frontend contract tests with `--confcutdir=tests/frontend`.
2. Run `git diff --check` on scoped changes.
3. Inspect the final diff and confirm no backend, `Chat.vue`, deployment, or unrelated worktree changes were introduced.

No commit or staging is part of this plan.
