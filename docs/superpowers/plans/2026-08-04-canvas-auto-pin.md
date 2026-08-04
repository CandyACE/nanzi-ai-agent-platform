# 画布打开后自动钉住 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every successful canvas open automatically pin the canvas while preserving manual unpinning until the next open.

**Architecture:** Move the pin state into the shared `useWorkspaceCanvas` composable so all canvas entry points share one lifecycle. `EmbedChat.vue` and `AgentDebug.vue` bind `ChatCanvas` directly to the composable's returned `canvasPinned` ref; the existing button remains the user-controlled toggle.

**Tech Stack:** Vue 3 Composition API, TypeScript, pytest-driven Node/TypeScript contract tests.

---

### Task 1: Add the failing lifecycle regression

**Files:**
- Modify: `tests/frontend/test_chat_shared_helpers_behavior.py`
- Test: `frontend/src/composables/chat/useWorkspaceCanvas.ts`

- [ ] **Step 1: Extend the existing workspace canvas behavior test**

Assert that a successful open sets `canvasPinned` to `true`, changing it to `false` keeps it false while the canvas remains open, and closing/reopening sets it back to `true`.

- [ ] **Step 2: Run the focused test and verify it fails**

Run `venv/bin/python -m pytest -q tests/frontend/test_chat_shared_helpers_behavior.py -k workspace_canvas`.

Expected: failure because `canvasPinned` is not yet exposed by `useWorkspaceCanvas`.

### Task 2: Implement shared auto-pinning

**Files:**
- Modify: `frontend/src/composables/chat/useWorkspaceCanvas.ts`

- [ ] **Step 1: Add and expose `canvasPinned`**

Create `const canvasPinned = ref(false)` beside the existing canvas lifecycle refs and return it from the composable.

- [ ] **Step 2: Pin only after successful opens**

Set `canvasPinned.value = true` alongside each successful `canvasVisible.value = true` path, including workspace previews, compare previews, local file previews, and direct payloads. Do not set it for failed loads or office-file downloads.

- [ ] **Step 3: Run the focused regression**

Run `venv/bin/python -m pytest -q tests/frontend/test_chat_shared_helpers_behavior.py -k workspace_canvas`.

Expected: PASS.

### Task 3: Bind both chat surfaces to the shared state

**Files:**
- Modify: `frontend/src/views/EmbedChat.vue`
- Modify: `frontend/src/views/AgentDebug.vue`

- [ ] **Step 1: Use the returned shared ref**

Destructure `canvasPinned` from `useWorkspaceCanvas` in each view and remove the duplicate local `ref(false)` declaration.

- [ ] **Step 2: Verify the existing component contract**

Run `venv/bin/python -m pytest -q tests/frontend/test_chat_canvas_resizer_contract.py tests/frontend/test_chat_surface_refactor_contract.py`.

Expected: PASS.

### Task 4: Run final validation

**Files:**
- Verify: changed files only

- [ ] **Step 1: Run the focused frontend tests**

Run `venv/bin/python -m pytest -q tests/frontend/test_chat_shared_helpers_behavior.py tests/frontend/test_chat_canvas_resizer_contract.py tests/frontend/test_chat_surface_refactor_contract.py`.

- [ ] **Step 2: Check patch hygiene**

Run `git diff --check` and inspect `git diff --stat`.
