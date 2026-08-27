# DeepSeek V4 Thinking Tool Compatibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make DeepSeek V4 honor the session thinking toggle and avoid thinking-mode tool-choice 400s without changing persisted model defaults.

**Architecture:** Add provider-aware request-body construction inside the existing AgentScope OpenAI-compatible adapter. DeepSeek V4 receives the official `extra_body.thinking` object; other providers retain the existing `chat_template_kwargs` path. Keep tool-choice decisions request-scoped and preserve exact-error-only fallback behavior.

**Tech Stack:** Python 3.11, AgentScope OpenAI-compatible model, pytest, Pydantic model parameters.

---

### Task 1: Add failing DeepSeek request-body tests

**Files:**
- Modify: `tests/ai/runtime/test_agentscope_llm_factory.py` near the existing `test_openai_chat_model_injects_chat_template_kwargs` tests

- [x] **Step 1: Add a fake OpenAI client test for DeepSeek V4 disabled thinking**

Add a test that creates `AgentScopeModelConfig(provider="deepseek", model="deepseek-v4-pro", thinking_enable=False, thinking_capable=True)`, calls `_call_api`, and asserts:

```python
assert captured["extra_body"] == {"thinking": {"type": "disabled"}}
assert "chat_template_kwargs" not in captured["extra_body"]
```

- [x] **Step 2: Add the enabled-thinking assertion**

Add a parameterized case for the same provider/model with `thinking_enable=True` and `reasoning_effort="high"`; assert:

```python
assert captured["extra_body"] == {"thinking": {"type": "enabled"}}
assert captured["reasoning_effort"] == "high"
```

- [x] **Step 3: Verify the tests fail for the current implementation**

Run:

```bash
venv/bin/python -m pytest tests/ai/runtime/test_agentscope_llm_factory.py -q
```

Expected: the new DeepSeek assertions fail because the current adapter emits `chat_template_kwargs` with `thinking` and `enable_thinking` instead of `thinking.type`.

### Task 2: Implement provider-aware DeepSeek request-body construction

**Files:**
- Modify: `app/services/ai/runtime/agentscope/models.py:53-99`
- Modify: `app/services/ai/runtime/agentscope/models.py:121-153`

- [x] **Step 1: Add a DeepSeek V4 detector and request-body helper**

Implement helpers with these rules:

```python
def _is_deepseek_v4(config: AgentScopeModelConfig) -> bool:
    provider = str(config.provider or "").strip().lower()
    model = str(config.model or "").strip().lower()
    return provider == "deepseek" and model in {"deepseek-v4-pro", "deepseek-v4-flash"}


def _request_extra_body(config: AgentScopeModelConfig) -> dict[str, Any] | None:
    if _is_deepseek_v4(config):
        return {"thinking": {"type": "enabled" if config.thinking_enable else "disabled"}}
    template_kwargs = _chat_template_kwargs(config)
    return {"chat_template_kwargs": template_kwargs} if template_kwargs else None
```

- [x] **Step 2: Store and merge the selected body in the adapter**

Store the helper result on `PlatformOpenAIChatModel` as a request-body dictionary. In `_call_api_once`, merge it into any caller-provided `extra_body` without overwriting unrelated fields. DeepSeek’s `thinking` object must take precedence over a stale caller-provided thinking object for this model instance.

- [x] **Step 3: Keep fallback state consistent**

When the exact thinking/tool-choice 400 fallback copies the model, update the copied request body to:

```python
fallback._request_extra_body = {
    **fallback._request_extra_body,
    "thinking": {"type": "disabled"},
}
```

Remove any stale `chat_template_kwargs.reasoning_effort` from the fallback body, while preserving the original model’s parameters and body.

- [x] **Step 4: Run the focused tests**

Run:

```bash
venv/bin/python -m pytest tests/ai/runtime/test_agentscope_llm_factory.py -q
```

Expected: all AgentScope factory tests pass, including the new DeepSeek cases and existing non-DeepSeek/fallback cases.

### Task 3: Add regression coverage for forced tools with thinking disabled

**Files:**
- Modify: `tests/ai/runtime/test_agentscope_llm_factory.py` alongside the request-body tests

- [x] **Step 1: Add request-capture coverage for `tool_choice`**

Create a fake completion client that records the request and returns a successful empty response. Call the DeepSeek V4 model with one function schema and `ToolChoice(mode="execute_sql_query")` while `thinking_enable=False`; assert the request contains the named function `tool_choice` and `extra_body.thinking.type == "disabled"`.

Also cover the complementary enabled-thinking case: the adapter omits a forced `tool_choice` before the provider request.

- [x] **Step 2: Verify the regression test passes**

Run:

```bash
venv/bin/python -m pytest tests/ai/runtime/test_agentscope_llm_factory.py -q
```

Expected: PASS, proving the fix does not remove deterministic tool preflight when thinking is explicitly disabled.

### Task 4: Run scoped regression checks and report deployment boundary

**Files:**
- Inspect only: `app/services/ai/runtime/agentscope/models.py`, `tests/ai/runtime/test_agentscope_llm_factory.py`

- [x] **Step 1: Run related reasoning and tool-choice tests**

Run:

```bash
venv/bin/python -m pytest \
  tests/ai/runtime/test_agentscope_llm_factory.py \
  tests/ai/runtime/test_reasoning_request_config.py \
  tests/ai/runners/test_tool_loop_config_loading.py -q
```

Expected: the selected tests pass, or any unrelated baseline collection/failure is reported separately.

- [x] **Step 2: Run syntax and whitespace checks**

Run:

```bash
venv/bin/python -m compileall -q app/services/ai/runtime/agentscope/models.py
git diff --check -- app/services/ai/runtime/agentscope/models.py tests/ai/runtime/test_agentscope_llm_factory.py
```

Expected: both commands exit successfully.

- [x] **Step 3: Recheck worktree scope**

Run:

```bash
git status --short
git diff --stat -- app/services/ai/runtime/agentscope/models.py tests/ai/runtime/test_agentscope_llm_factory.py
```

Expected: only the requested adapter/test changes and the two new uncommitted planning documents are attributed to this task; existing Excel and conversation-boundary changes remain untouched.

- [x] **Step 4: State live-environment limitation**

Do not run `./dev.sh` or deployment scripts. Tell the user to restart the backend/frontend in their console and verify the provider request contains `extra_body.thinking.type=disabled`; local tests do not prove the currently running service has loaded the change.
