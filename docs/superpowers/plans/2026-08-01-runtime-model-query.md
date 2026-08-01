# 运行时模型查询 Implementation Plan

> **For agentic workers:** Execute this plan task-by-task in the current session with TDD checkpoints.

**Goal:** Make model self-identification reliable by exposing one runtime model resolver, direct platform answers for model-identity questions, and a read-only `get_current_model` system tool.

**Architecture:** Resolve the selected model and registry alias in `AgentConfigProvider` once per turn. Store only non-sensitive model metadata in the request-scoped `AgentContext`; use it for the implicit tool and for the direct-answer branch. Keep API credentials inside the LLM factory path and never return them from the resolver's public payload.

**Tech Stack:** Python, pytest/pytest-asyncio, Pydantic `AgentContext`, existing `FunctionTool`/`ToolRegistry`, AgentService streaming SSE.

---

### Task 1: Define the runtime model contract and routing predicate

**Files:**
- Create: `tests/ai/test_runtime_model_info.py`
- Modify: `tests/ai/test_request_decision.py`
- Modify: `app/services/ai/intent_service.py`
- Modify: `app/services/ai/request_decision.py` only if the new predicate needs a routing boundary assertion

- [ ] **Step 1: Write failing tests**

Add tests for a runtime model payload that distinguishes `configured_model`, `effective_model_id`, `source`, `phase`, `is_fallback`, and `resolution_status`, and add parametrized self-identification queries such as `你当前的模型是什么`, `本轮用了哪个模型`, and `what model are you using`.

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
venv/bin/python -m pytest tests/ai/test_runtime_model_info.py tests/ai/test_request_decision.py -q
```

Expected: collection or assertion failures because the runtime contract and predicate do not yet exist.

- [ ] **Step 3: Implement the smallest pure contract/predicate**

Add a small immutable runtime model metadata type and a narrowly-scoped `looks_like_current_model_query()` predicate. Extend platform self-service detection through this predicate without broadening all model configuration questions into direct model answers.

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run the same pytest command and expect all new and existing request-decision tests to pass.

### Task 2: Centralize model selection and registry resolution

**Files:**
- Modify: `app/services/ai/config.py`
- Modify: `tests/ai/test_runtime_model_info.py`
- Modify: `tests/ai/runtime/test_agentscope_llm_factory.py` if existing factory expectations need explicit coverage

- [ ] **Step 1: Add failing async resolution tests**

Cover agent-config selection, debug override, system default, registered alias resolution, direct model IDs, and registry lookup failure. Assert that public metadata contains no `api_key` or `base_url` keys.

- [ ] **Step 2: Run only the new resolver tests and verify RED**

Run:

```bash
venv/bin/python -m pytest tests/ai/test_runtime_model_info.py -q
```

Expected: failures for the missing shared resolver or missing fields.

- [ ] **Step 3: Implement the shared resolver and reuse it from `get_configured_llm()`**

Keep the existing priority order: explicit override, debug model, agent config, system default. Resolve active `AIModel.name` aliases to `AIModel.model_id`; preserve credentials only in the internal selection object used by `get_configured_llm()`. The public `RuntimeModelInfo` must be serializable without secrets.

- [ ] **Step 4: Run resolver and LLM factory tests**

Run:

```bash
venv/bin/python -m pytest tests/ai/test_runtime_model_info.py tests/ai/runtime/test_agentscope_llm_factory.py -q
```

Expected: PASS, with existing factory behavior preserved.

### Task 3: Make runtime metadata available to tools

**Files:**
- Modify: `app/core/context.py`
- Modify: `app/services/ai/context_manager.py`
- Modify: `app/services/ai/tools/system_tools.py`
- Modify: `app/services/ai/tools/registry.py`
- Modify: `app/services/ai/runtime/agentscope/tools.py`
- Create: `tests/ai/tools/test_current_model_tool.py`
- Modify: `tests/ai/tools/test_registry.py`

- [ ] **Step 1: Write failing tool/context tests**

Assert that `get_current_model` returns the stored public metadata, returns a deterministic unavailable status when no request context exists, is present in `SYSTEM_IMPLICIT_TOOLS`, is read-only, and is included in runtime tool specs without exposing credentials.

- [ ] **Step 2: Run the focused tool tests and verify RED**

Run:

```bash
venv/bin/python -m pytest tests/ai/tools/test_current_model_tool.py tests/ai/tools/test_registry.py -q
```

Expected: import/registration/assertion failures.

- [ ] **Step 3: Implement context propagation and registration**

Add a `runtime_model_info` dictionary to `AgentContext`, pass the resolver's public payload through `AgentContextManager.setup_context()`, implement the no-argument read-only tool, register it as a system implicit tool, add runtime evidence type `RUNTIME_STATE`, and add it to `READ_ONLY_TOOL_NAMES` plus the platform tool inventory description.

- [ ] **Step 4: Run the focused tool tests and existing system-tool tests**

Run:

```bash
venv/bin/python -m pytest tests/ai/tools/test_current_model_tool.py tests/ai/tools/test_registry.py tests/ai/executors/test_system_tools_injection.py -q
```

Expected: PASS.

### Task 4: Directly answer model-identity questions in AgentService

**Files:**
- Modify: `app/services/ai/agent_service.py`
- Modify: `app/services/ai/agent_prompts.py`
- Modify: `tests/services/ai/test_agent_service_model_query.py`

- [ ] **Step 1: Write a failing service-level regression test**

Exercise the direct-answer helper/branch with a configured model and debug override. Assert that the response includes the effective model ID, no normal executor is called, and the response is emitted as normal successful content with a model meta payload.

- [ ] **Step 2: Run the regression test and verify RED**

Run:

```bash
venv/bin/python -m pytest tests/services/ai/test_agent_service_model_query.py -q
```

Expected: failure because model-identity questions still proceed to normal model generation.

- [ ] **Step 3: Implement the direct-answer path**

After agent configuration and runtime model resolution, detect only `looks_like_current_model_query()`. Emit a safe `meta` event with configured/effective model fields, emit the localized answer, set the turn content/status so audit and conversation persistence remain correct, and skip executor/model generation. Preserve the existing route/permission checks and do not expose credentials.

- [ ] **Step 4: Run the service regression and adjacent routing tests**

Run:

```bash
venv/bin/python -m pytest tests/services/ai/test_agent_service_model_query.py tests/ai/test_request_decision.py tests/ai/test_router_context.py -q
```

Expected: PASS.

### Task 5: Full targeted verification and handoff

**Files:**
- No additional source files expected.

- [ ] **Step 1: Run all touched-area tests**

```bash
venv/bin/python -m pytest \
  tests/ai/test_runtime_model_info.py \
  tests/ai/test_request_decision.py \
  tests/ai/tools/test_current_model_tool.py \
  tests/ai/tools/test_registry.py \
  tests/ai/executors/test_system_tools_injection.py \
  tests/services/ai/test_agent_service_model_query.py \
  tests/ai/runtime/test_agentscope_llm_factory.py -q
```

- [ ] **Step 2: Check the diff without staging or committing**

Run:

```bash
git diff --check
git status --short
```

Confirm the unrelated existing change in `app/services/task_notification_delivery.py` remains untouched.

- [ ] **Step 3: Report verification boundaries**

Report targeted test results separately from any broad-suite baseline failures. Explicitly state that `./dev.sh`, live provider calls, deployment, and browser acceptance were not run by the agent.
