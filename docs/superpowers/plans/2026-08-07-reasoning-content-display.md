# Reasoning Content Display Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stream provider reasoning separately from the final answer and render it in dedicated thinking panels in EmbedChat and AgentDebug.

**Architecture:** AgentScope event mapping emits `reasoning_content` deltas for thinking blocks. The shared frontend SSE model and dispatcher accumulate these deltas into `reasoningContent`; each chat surface renders that field separately while keeping platform logs and normal Markdown output unchanged.

**Tech Stack:** Python 3.11, FastAPI/AgentScope, Vue 3, TypeScript, Tailwind CSS, pytest, Vue contract tests.

---

### Task 1: Add failing backend event-mapping coverage

**Files:**
- Modify: `tests/ai/runtime/test_event_stream_observability.py`
- Test: `app/services/ai/runtime/agentscope/event_stream.py`

- [ ] **Step 1: Write a failing test for reasoning deltas.**

Add a test that creates a minimal event with `type="THINKING_BLOCK_DELTA"` and `delta="先分析"`, consumes `map_standard_agentscope_event`, and asserts the result contains exactly `{"type": "reasoning_content", "content": "先分析"}` plus the existing thinking status event if the current contract emits it.

- [ ] **Step 2: Run only the new test and verify it fails for the missing field.**

Run:

```bash
venv/bin/python -m pytest tests/ai/runtime/test_event_stream_observability.py -k reasoning_content -q
```

Expected: FAIL because the mapper currently emits only a thinking status event and no reasoning text.

### Task 2: Emit reasoning content from the shared AgentScope mapper

**Files:**
- Modify: `app/services/ai/runtime/agentscope/event_stream.py:400-440`

- [ ] **Step 1: Emit the thinking delta without changing normal answer events.**

For `THINKING_BLOCK_DELTA`, read `event.delta`, and yield `{"type": "reasoning_content", "content": delta}` only when the delta is non-empty. Preserve the existing `{"type": "thinking", "status": "continuing"}` state signal.

- [ ] **Step 2: Run the backend event-stream test and verify it passes.**

Run:

```bash
venv/bin/python -m pytest tests/ai/runtime/test_event_stream_observability.py -k reasoning_content -q
```

Expected: PASS.

- [ ] **Step 3: Run the full targeted event-stream test module.**

Run:

```bash
venv/bin/python -m pytest tests/ai/runtime/test_event_stream_observability.py -q
```

Expected: PASS, with any unrelated baseline failures reported separately.

### Task 3: Add failing shared frontend stream-contract coverage

**Files:**
- Modify: `tests/frontend/test_chat_shared_helpers_behavior.py`
- Test: `frontend/src/utils/agentscopeSseHandlers.ts`

- [ ] **Step 1: Add a failing behavior assertion for the reasoning field.**

Assert that the shared stream message type exposes `reasoningContent`, and that a `reasoning_content` event is consumed by the dispatcher and appended without changing `content`.

- [ ] **Step 2: Run the new behavior test and verify it fails.**

Run:

```bash
venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_chat_shared_helpers_behavior.py -k reasoning -q
```

Expected: FAIL because the shared type and dispatcher do not yet handle the event.

### Task 4: Implement shared frontend reasoning accumulation

**Files:**
- Modify: `frontend/src/utils/agentscopeSseHandlers.ts:75-91,456-532`
- Modify: `frontend/src/views/EmbedChat.vue:2350-2370`
- Modify: `frontend/src/views/AgentDebug.vue:1210-1235`

- [ ] **Step 1: Add the shared `reasoningContent?: string` field.**

Add the field to `AgentStreamMessage` and both page-local `Message` interfaces.

- [ ] **Step 2: Add a dispatcher case for `reasoning_content`.**

Append `String(data.content || "")` to `msg.reasoningContent`, consume the event, and leave `msg.content` untouched. Ignore empty deltas.

- [ ] **Step 3: Run the shared frontend contract test and verify it passes.**

Run:

```bash
venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_chat_shared_helpers_behavior.py -k reasoning -q
```

Expected: PASS.

### Task 5: Add dedicated thinking panels to both chat surfaces

**Files:**
- Modify: `frontend/src/views/EmbedChat.vue` near the existing thinking/log panel
- Modify: `frontend/src/views/AgentDebug.vue` near the existing thinking/log panel

- [ ] **Step 1: Add the failing page contract assertions to `tests/frontend/test_model_thinking_config_contract.py`.**

Extend the frontend contract test to assert both pages reference `reasoningContent`, show a “思考过程” label, and render the reasoning field separately from `MessageRenderer`’s ordinary `content` prop.

- [ ] **Step 2: Run the page contract tests and verify they fail.**

Run:

```bash
venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_model_thinking_config_contract.py -k reasoning -q
```

Expected: FAIL because the page templates do not yet render the field.

- [ ] **Step 3: Implement the separate panel in EmbedChat and AgentDebug.**

Render only when `msg.reasoningContent` is non-empty; the `isThinking` status alone must not create an empty card. Use a compact bordered card with a “思考过程” header, scrollable body, and the existing shared Markdown renderer. Keep the existing execution-log accordion as a separate sibling section.

- [ ] **Step 4: Run the page contract tests and verify they pass.**

Run:

```bash
venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_model_thinking_config_contract.py -k reasoning -q
```

Expected: PASS.

### Task 6: Type-check and regression verification

**Files:**
- No new files.

- [ ] **Step 1: Run the targeted frontend contract suite.**

```bash
venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend -q
```

- [ ] **Step 2: Run Vue type checking.**

```bash
cd frontend && node_modules/.bin/vue-tsc --noEmit
```

Expected: no new errors attributable to the reasoning display changes.

- [ ] **Step 3: Run the backend targeted tests.**

```bash
cd /Users/chenxiaolong/workspace/nanzi-ai-agent-platform && venv/bin/python -m pytest tests/ai/runtime/test_event_stream_observability.py -q
```

- [ ] **Step 4: Review the final diff.**

```bash
git diff --check
git diff --stat
git status --short
```

Do not start services, deploy, stage, or commit unless separately requested.
