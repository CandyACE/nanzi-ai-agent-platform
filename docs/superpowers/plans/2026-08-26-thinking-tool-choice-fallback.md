# Thinking Tool Choice Fallback Implementation Plan

> **For agentic workers:** Execute this plan task-by-task with a test-first loop and preserve unrelated worktree changes.

**Goal:** When an OpenAI-compatible provider rejects a forced `tool_choice` while thinking is enabled, retry the current request once with thinking disabled without changing persisted model configuration or shared model state.

**Architecture:** Keep the existing pre-call `tool_choice` compatibility layer. Add a narrow fallback at the platform-owned `PlatformOpenAIChatModel._call_api` boundary, where the provider `BadRequestError` and both thinking control layers are visible. Use a shallow model copy with copied AgentScope parameters and provider template kwargs so the fallback request cannot mutate the original model used by concurrent or later calls.

**Tech Stack:** Python 3.11, AgentScope OpenAIChatModel, OpenAI SDK, pytest, pytest-asyncio.

---

### Task 1: Add the failing fallback regression test

**Files:**
- Modify: `tests/ai/runtime/test_agentscope_llm_factory.py`
- Test target: `PlatformOpenAIChatModel._call_api` created by `create_openai_chat_model`

- [x] **Step 1: Add a fake OpenAI client that rejects the first request.**

The fake completion client records each request. On the first call it raises `openai.BadRequestError` with HTTP 400 and the provider message mentioning `tool_choice`, `required`, and thinking mode. On the second call it returns an empty non-stream response.

- [x] **Step 2: Add one behavior test.**

Create a thinking-enabled model with `reasoning_effort="high"`, call `_call_api` with `ToolChoice(mode="execute_sql_query")`, and assert the second request has:

```python
assert second["tool_choice"] == {"type": "function", "function": {"name": "execute_sql_query"}}
assert second["extra_body"] == {
    "chat_template_kwargs": {"thinking": False, "enable_thinking": False}
}
assert "reasoning_effort" not in second
assert model.parameters.thinking_enable is True
assert model.parameters.reasoning_effort == "high"
```

- [x] **Step 3: Run only the new test and verify RED.**

Run:

```bash
PYTHONPATH=. venv/bin/python -m pytest tests/ai/runtime/test_agentscope_llm_factory.py -k "thinking_tool_choice_fallback" -q
```

Expected: FAIL because the current platform model re-raises the provider `BadRequestError` and makes only one request.

### Task 2: Add negative-path regression coverage

**Files:**
- Modify: `tests/ai/runtime/test_agentscope_llm_factory.py`

- [x] **Step 1: Add a non-matching 400 test.**

Make the fake client raise a 400 whose message is `invalid model parameter` without the `tool_choice`/thinking markers. Assert the exception is raised and only one request is made.

- [x] **Step 2: Add a non-forced-choice test.**

Use `tool_choice=None` with a matching-looking provider error and assert no fallback is attempted; the original exception remains visible.

- [x] **Step 3: Run the new negative tests and verify RED.**

Run:

```bash
PYTHONPATH=. venv/bin/python -m pytest tests/ai/runtime/test_agentscope_llm_factory.py -k "thinking_tool_choice_fallback or non_matching_tool_choice_error" -q
```

Expected: the positive fallback test fails while the negative tests establish that the current implementation does not incorrectly retry unrelated errors.

### Task 3: Implement the narrow request-level fallback

**Files:**
- Modify: `app/services/ai/runtime/agentscope/models.py`

- [x] **Step 1: Add a provider-error predicate.**

Match only an OpenAI `BadRequestError` with status 400 when available, `tool_choice` in the combined exception/body text, a thinking/reasoning marker (including the provider's common `thirking` typo), and a forced non-`auto` choice. Do not match generic 400s.

- [x] **Step 2: Add a shallow fallback copy.**

Copy the model instance, use `parameters.model_copy(update={"thinking_enable": False, "reasoning_effort": None})`, and replace only the copied `_chat_template_kwargs` with `thinking=False`, `enable_thinking=False`, and no `reasoning_effort`. Reuse the original client, formatter, credentials, and transport.

- [x] **Step 3: Retry exactly once from `_call_api`.**

Catch only the matching `BadRequestError`, log a warning with model and fallback reason, invoke the parent `OpenAIChatModel._call_api` on the copied model with the original messages, tools, tool choice, and generation kwargs, and re-raise every other exception.

- [x] **Step 4: Run the positive and negative tests and verify GREEN.**

Run:

```bash
PYTHONPATH=. venv/bin/python -m pytest tests/ai/runtime/test_agentscope_llm_factory.py -k "thinking_tool_choice_fallback or non_matching_tool_choice_error" -q
```

Expected: all fallback tests PASS, including the assertion that the original model remains thinking-enabled.

### Task 4: Run focused regression checks

**Files:**
- No additional files.

- [x] **Step 1: Run all AgentScope runtime tests related to reasoning and tool-choice compatibility.**

```bash
PYTHONPATH=. venv/bin/python -m pytest \
  tests/ai/runtime/test_agentscope_llm_factory.py \
  tests/ai/runtime/test_tool_choice_thinking_compat.py \
  tests/ai/runtime/test_reasoning_request_config.py -q
```

- [x] **Step 2: Run syntax and diff checks.**

```bash
venv/bin/python -m compileall -q app/services/ai/runtime/agentscope/models.py tests/ai/runtime/test_agentscope_llm_factory.py
git diff --check -- app/services/ai/runtime/agentscope/models.py tests/ai/runtime/test_agentscope_llm_factory.py docs/superpowers/specs/2026-08-26-thinking-tool-choice-fallback-design.md docs/superpowers/plans/2026-08-26-thinking-tool-choice-fallback.md
```

- [x] **Step 3: Inspect status and report boundaries.**

Confirm the unrelated `frontend/src/views/PersonalCenter.vue` change remains untouched. Do not run `./dev.sh`, service startup, deployment, or real model-router traffic in this task.
