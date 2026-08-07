# Chat Thinking Menu Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a shared model-menu thinking submenu to EmbedChat and AgentDebug, with session-level AgentScope thinking overrides applied consistently by backend chat calls.

**Architecture:** Keep the existing shared `ChatInput` as the single UI entry point. Parent views own transient session overrides and add them to `debug_options`; the backend resolves the registered model once, validates the requested override against its capabilities, and passes `thinking_enable`/`reasoning_effort` through the existing AgentScope factory path used by primary, ChatBI, and auxiliary calls.

**Tech Stack:** Vue 3 + TypeScript + Tailwind CSS, FastAPI + Pydantic 2, pytest contract tests, AgentScope 2.x.

---

### Task 1: Define the session override contract

**Files:**
- Modify: `tests/ai/runtime/test_reasoning_request_config.py`
- Modify: `tests/frontend/test_model_thinking_config_contract.py`
- Create: `docs/superpowers/plans/2026-08-07-chat-thinking-menu.md`

- [x] **Step 1: Write failing tests** for valid effort overrides, allowed per-turn disable, rejection of unsupported effort, and both chat views passing session fields.
- [x] **Step 2: Run the focused tests** and confirm they fail because the request-level override and UI bindings do not yet exist.

### Task 2: Apply validated request overrides in the shared backend path

**Files:**
- Create: `app/services/ai/reasoning.py`
- Modify: `app/services/ai/config.py`
- Modify: `app/core/llm/client.py` if the shared async factory needs request-scoped propagation
- Modify: `tests/ai/runtime/test_reasoning_request_config.py`

- [x] **Step 1: Read `thinking_enable` and `reasoning_effort` from request debug context.**
- [x] **Step 2: Resolve the selected/default registered model and validate overrides against `allow_disable_thinking` and `supported_reasoning_efforts`.**
- [x] **Step 3: Preserve registered defaults when no override is present; use `None` for automatic reasoning effort.**
- [x] **Step 4: Pass the effective values through every existing `AgentConfigProvider` call without changing individual runners.**
- [x] **Step 5: Run backend tests and confirm the new tests pass.**

### Task 3: Build the shared ChatInput secondary menu

**Files:**
- Modify: `frontend/src/components/embed/ChatInput.vue`
- Modify: `frontend/src/api/model.ts` only if shared UI types need a new exported helper
- Modify: `tests/frontend/test_model_thinking_config_contract.py`

- [x] **Step 1: Add session override props/events and derive the selected model capability state.**
- [x] **Step 2: Extend the model dropdown with a nested thinking settings panel.**
- [x] **Step 3: Show only supported AgentScope effort options, mark the active session choice, and show “关闭思考” only when allowed.**
- [x] **Step 4: Reset incompatible session overrides when the model changes and keep the default model option compatible with the existing dropdown.**
- [x] **Step 5: Keep desktop and narrow/mobile layouts within the existing popover boundaries.**

### Task 4: Wire EmbedChat and AgentDebug request state

**Files:**
- Modify: `frontend/src/views/EmbedChat.vue`
- Modify: `frontend/src/views/AgentDebug.vue`
- Modify: `tests/frontend/test_model_thinking_config_contract.py`

- [x] **Step 1: Add transient `thinkingEnableOverride` and `reasoningEffortOverride` state to both views.**
- [x] **Step 2: Pass state and update handlers to the shared `ChatInput`.**
- [x] **Step 3: Add only explicit session overrides to each completion request’s `debug_options`.**
- [x] **Step 4: Clear overrides when the selected model changes or a new model session starts.**

### Task 5: Verify and review

**Files:**
- No additional production files.

- [x] **Step 1: Run the focused backend/runtime and frontend contract tests.**
- [x] **Step 2: Run `vue-tsc --noEmit`, Python compilation, and `git diff --check`.**
- [x] **Step 3: Review the final diff for unrelated changes and report any broad-suite baseline failures separately.**
