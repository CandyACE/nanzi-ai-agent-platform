# 浏览器人工接管与刷新控制 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有服务端浏览器会话中实现人工接管、AI 操作阻断、操作期刷新控制、中文输入增强和验证码人工处理提示。

**Architecture:** 控制权只存于 `BrowserRuntime` 的 session 状态，不新增数据库迁移；Viewer WebSocket 负责广播控制状态，`BrowserPanel.vue` 负责刷新生命周期和用户提示。AI 的 `browser_click/fill` 在 Runtime 层统一检查控制权，所有 Playwright 输入仍经过现有 session lock。

**Tech Stack:** FastAPI WebSocket、Python asyncio、Playwright、Vue 3 + TypeScript、pytest、vue-tsc。

---

### Task 1: 固化 Runtime 控制权行为

**Files:**
- Modify: `app/services/ai/browser/browser_runtime.py`
- Modify: `app/services/ai/browser/browser_worker.py`
- Test: `tests/services/ai/test_browser_runtime.py`
- Test: `tests/services/ai/test_browser_worker.py`

- [ ] **Step 1: Write failing tests** for human takeover, AI blocking, release, session isolation, and text insertion.
- [ ] **Step 2: Run the focused tests and verify they fail because control state and text insertion are missing.**
- [ ] **Step 3: Add per-session control state plus an asyncio release event, `acquire_human_control()`, `release_human_control()`, and `control_state()` to `BrowserRuntime`; make `click()` and `fill()` wait while preserving the existing session lock.
- [ ] **Step 4: Mark manual events as human-owned and use Playwright text insertion for `text`; keep `key` for shortcut keys.
- [ ] **Step 5: Run the focused Runtime/Worker tests and verify they pass.**

### Task 2: Add Viewer control-state protocol

**Files:**
- Modify: `app/api/v1/endpoints/browser.py`
- Modify: `tests/api/v1/test_browser_sessions.py`
- Modify: `tests/services/ai/test_browser_events.py`

- [ ] **Step 1: Write failing source/endpoint tests** for `control_state`, `release_control`, disconnect cleanup, and captcha messages.
- [ ] **Step 2: Run the focused endpoint tests and verify they fail because the new events are not handled.**
- [ ] **Step 3: Emit current control state after Viewer connection and after human events; handle `release_control`; release control in WebSocket disconnect cleanup.
- [ ] **Step 4: Keep AI-originated semantic operations suspended while human control is active; do not execute Playwright actions or surface an internal exception to the model.
- [ ] **Step 5: Run endpoint and browser event tests.**

### Task 3: Add conservative captcha detection

**Files:**
- Modify: `app/services/ai/browser/browser_worker.py`
- Modify: `app/services/ai/browser/browser_runtime.py`
- Test: `tests/services/ai/test_browser_worker.py`
- Test: `tests/services/ai/test_browser_runtime.py`

- [ ] **Step 1: Write failing tests** for explicit slider/security-verification markers and ordinary business text that must not trigger captcha mode.
- [ ] **Step 2: Run the focused tests and verify the detector is absent.**
- [ ] **Step 3: Implement bounded DOM/text checks that only produce a human-help signal; never calculate or solve a challenge.
- [ ] **Step 4: Include captcha state in the snapshot/control response and run the focused tests.**

### Task 4: Implement frontend handoff and refresh lifecycle

**Files:**
- Modify: `frontend/src/components/embed/BrowserPanel.vue`
- Modify: `tests/frontend/test_browser_panel_contract.py`

- [ ] **Step 1: Write failing contract assertions** for current owner text, “交还 AI”, captcha notice, interaction pause, and text insertion/paste behavior.
- [ ] **Step 2: Run the frontend contract test and verify it fails.**
- [ ] **Step 3: Add `controlOwner`, `captchaDetected`, `interactionInProgress`, `releaseControl()`, and `syncRefreshAfterInteraction()`; pause only after pointer down or an actual input send, not on hover.
- [ ] **Step 4: Update the input dialog for Chinese text, paste, Enter, shortcut keys, and clear human/captcha status copy.
- [ ] **Step 5: Run frontend contract tests and `vue-tsc --noEmit`.**

### Task 5: Integration verification and handoff

**Files:**
- Modify: `tests/CHECKLIST.md` only if the verified browser behavior description needs updating.

- [ ] **Step 1: Run the complete browser-related pytest set.**
- [ ] **Step 2: Run `vue-tsc --noEmit` from `frontend/`.**
- [ ] **Step 3: Run `git diff --check` and inspect `git status --short`; preserve unrelated worktree edits and do not stage or commit.**
- [ ] **Step 4: Report exact test results and remind the user to restart services manually.**
