# Model Fallback Notice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a visible and persistent warning appear before an assistant answer when AgentScope switches from the primary model to its configured fallback model.

**Architecture:** Detect the actual `current_model` selected by AgentScope in the existing model-call middleware, store one request-local marker on the Agent, and translate that marker into one `model_fallback` SSE event at the shared AgentScope event boundary. The shared frontend SSE dispatcher prepends the warning for both chat surfaces, while the server stream accumulator includes the event in persisted assistant content.

**Tech Stack:** Python 3.11, AgentScope middleware/events, FastAPI SSE dictionaries, Vue 3 + TypeScript, pytest frontend contract tests.

---

### Task 1: Lock the fallback signal and persistence contract with failing tests

**Files:**
- Modify: `tests/ai/runtime/test_model_fallback_notice.py`
- Modify: `tests/ai/runtime/test_process_narration.py`
- Create: `tests/frontend/test_model_fallback_notice_contract.py`

- [x] **Step 1: Test fallback detection and one-time SSE emission**

Cover an Agent whose primary model is `deepseek-v4-pro`, a current model `gemma-4-31b`, and a normal text event. Assert that the shared event mapping emits one `model_fallback` event with both names, and a second event mapping does not emit it again for the same stream state.

- [x] **Step 2: Test persisted answer accumulation**

Pass `{"type": "model_fallback", "content": "> warning"}` to `accumulate_visible_answer` and assert the returned answer contains the warning. Existing ordinary answer and reasoning behavior must remain unchanged.

- [x] **Step 3: Test the shared frontend contract**

Assert `agentscopeSseHandlers.ts` defines the fallback message field, handles `case "model_fallback"`, prepends the event content, and adds a warning log. Assert both `EmbedChat.vue` and `AgentDebug.vue` continue to call `dispatchAgentscopeStreamEvent`.

- [x] **Step 4: Run the new tests and confirm RED**

Run:

```bash
venv/bin/python -m pytest tests/ai/runtime/test_model_fallback_notice.py tests/ai/runtime/test_process_narration.py tests/frontend/test_model_fallback_notice_contract.py -q
```

Expected: the new fallback tests fail because no marker/event/accumulation/frontend case exists yet; unrelated existing tests should still collect.

### Task 2: Detect actual fallback selection and emit the server event

**Files:**
- Modify: `app/services/ai/runtime/agentscope/middleware.py`
- Modify: `app/services/ai/runtime/agentscope/event_stream.py`
- Modify: `app/services/ai/runtime/agentscope/event_stream.py` stream state initialization

- [x] **Step 1: Record the selected fallback model in middleware**

At the beginning of `ModelCallStatsMiddleware.on_model_call`, compare `current_model` by identity with `agent.model`. When they differ, set an ephemeral `_platform_fallback_info` mapping on the Agent only if it is not already present:

```python
{
    "primary_model": str(getattr(agent.model, "model", "unknown") or "unknown"),
    "fallback_model": str(getattr(current_model, "model", "unknown") or "unknown"),
}
```

Do not alter the model, retry count, or middleware return value.

- [x] **Step 2: Add a one-time fallback notice to the shared event mapper**

Before mapping the incoming AgentScope event, read the marker from `agent`. If it exists and `state["model_fallback_notice_emitted"]` is false, set the flag and yield:

```python
{
    "type": "model_fallback",
    "status": "warning",
    "primary_model": primary_model,
    "fallback_model": fallback_model,
    "content": (
        f"> ⚠️ 主模型 `{primary_model}` 调用失败，"
        f"本次回答由 fallback 模型 `{fallback_model}` 生成。"
    ),
}
```

If there is no marker, yield no event. Keep the existing AgentScope event mapping unchanged.

- [x] **Step 3: Run backend tests**

Run:

```bash
venv/bin/python -m pytest tests/ai/runtime/test_model_fallback_notice.py tests/ai/runtime/test_process_narration.py -q
```

Expected: PASS.

### Task 3: Make the warning visible in both chat surfaces and history

**Files:**
- Modify: `app/services/ai/runtime/agentscope/process_narration.py`
- Modify: `frontend/src/utils/agentscopeSseHandlers.ts`
- Test: `tests/frontend/test_model_fallback_notice_contract.py`

- [x] **Step 1: Include fallback notice in server-side answer accumulation**

Add `model_fallback` to the answer-like event types handled by `accumulate_visible_answer`, so the content passed to assistant persistence starts with the warning.

- [x] **Step 2: Handle the event in the shared frontend dispatcher**

Add `fallbackNotice?: string` to `AgentStreamMessage`. Implement a handler that deduplicates by the notice text, prepends the Markdown content to `msg.content`, and calls `addLog` with warning status and category `model`.

- [x] **Step 3: Route `model_fallback` through the shared dispatcher**

Add the event case in `dispatchAgentscopeStreamEvent`; no separate logic is needed in `EmbedChat.vue` or `AgentDebug.vue` because both already use the shared dispatcher.

- [x] **Step 4: Run frontend contract and backend accumulation tests**

Run:

```bash
venv/bin/python -m pytest tests/frontend/test_model_fallback_notice_contract.py tests/ai/runtime/test_model_fallback_notice.py tests/ai/runtime/test_process_narration.py -q
```

Expected: PASS.

### Task 4: Run scoped regression checks and report live verification boundary

**Files:**
- Inspect: `app/services/ai/runtime/agentscope/middleware.py`
- Inspect: `app/services/ai/runtime/agentscope/event_stream.py`
- Inspect: `app/services/ai/runtime/agentscope/process_narration.py`
- Inspect: `frontend/src/utils/agentscopeSseHandlers.ts`

- [x] **Step 1: Run focused fallback and existing AgentScope tests**

```bash
venv/bin/python -m pytest \
  tests/ai/runtime/test_model_fallback_notice.py \
  tests/ai/runtime/test_process_narration.py \
  tests/ai/runtime/test_agentscope_llm_factory.py \
  tests/frontend/test_model_fallback_notice_contract.py -q
```

- [x] **Step 2: Run whitespace and syntax checks**

```bash
venv/bin/python -m compileall -q app/services/ai/runtime/agentscope/middleware.py app/services/ai/runtime/agentscope/event_stream.py app/services/ai/runtime/agentscope/process_narration.py
git diff --check -- app/services/ai/runtime/agentscope/middleware.py app/services/ai/runtime/agentscope/event_stream.py app/services/ai/runtime/agentscope/process_narration.py frontend/src/utils/agentscopeSseHandlers.ts
```

- [x] **Step 3: Do not start services**

Tell the user to restart the backend/frontend manually and verify a forced fallback shows the warning before the answer, names both models, and remains visible after refreshing the conversation.
