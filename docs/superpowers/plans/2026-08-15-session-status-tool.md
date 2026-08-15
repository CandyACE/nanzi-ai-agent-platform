# Session Status Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a parameterless, read-only `session_status` system tool that gives the current AI a safe, source-aware snapshot of its active session and runtime environment.

**Architecture:** Build the snapshot in a focused `session_status.py` module from the current `AgentContext`, request debug context, runtime model metadata, and AgentScope workspace path resolvers. Register it through the existing system implicit tool path, mark it read-only, and classify it as runtime-state evidence. Do not add a frontend or persistent status API.

**Tech Stack:** Python 3.11, Pydantic/ContextVar, existing `@tool` compatibility wrapper, AgentScope runtime tool specs, pytest.

---

### Task 1: Lock the public tool and snapshot contract with failing tests

**Files:**
- Create: `tests/ai/tools/test_session_status.py`
- Modify: `tests/ai/executors/test_system_tools_injection.py:8-48`

- [ ] **Step 1: Write the failing tests**

Add tests that construct an `AgentContext`, set debug context with `injected_context`, patch workspace resolution and model statistics, and assert:

```python
def test_session_status_returns_safe_current_context_snapshot():
    payload = json.loads(session_status.invoke({}))
    assert payload["scope"] == "current_session"
    assert payload["session"]["conversation_id"] == "conv-1"
    assert payload["client"] == {
        "device_type": "移动端(小屏幕)",
        "display_hint": "窄屏排版优化",
        "source": "client_reported",
    }
    assert payload["workspace"]["session_workdir"]["path"] == "/data/user/sessions/conv-1"
    assert payload["workspace"]["docs_dir"]["path"] == "/data/user/docs"
    assert payload["model"]["context_window_tokens"] == 131072
    assert payload["context_usage"]["last_input_tokens"] == 1200
    assert payload["user"]["user_name"] == "alice"


def test_session_status_excludes_secrets_and_internal_objects():
    payload = json.loads(session_status.invoke({}))
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "api_key" not in serialized
    assert "base_url" not in serialized
    assert "engine_config" not in serialized
    assert "permission_options" not in serialized
    assert "/private/attachment" not in serialized


def test_session_status_is_parameterless_and_handles_missing_context():
    assert session_status.args_schema.model_fields == {}
    payload = json.loads(session_status.invoke({}))
    assert payload["scope"] == "current_session"
    assert payload["session"]["conversation_id"] is None
    assert payload["limitations"]
```

Also extend the implicit-tool test with `session_status`, and add a runtime-spec assertion that its permission scope is `read` and its evidence type is `RUNTIME_STATE`.

- [ ] **Step 2: Run the focused tests and verify the expected RED state**

Run:

```bash
pytest --confcutdir=tests/frontend tests/ai/tools/test_session_status.py tests/ai/executors/test_system_tools_injection.py -q
```

Expected: FAIL because `session_status` is not defined or registered yet.

### Task 2: Implement the safe snapshot builder

**Files:**
- Create: `app/services/ai/tools/session_status.py`

- [ ] **Step 1: Add the minimal implementation**

Implement `@tool async def session_status() -> str` with these rules:

- Read `get_current_agent_context()` and `get_debug_option("injected_context", {})` only.
- Return `schema_version=1`, `scope="current_session"`, and stable section names.
- Copy only explicit safe model fields: `configured_model`, `effective_model_id`, `source`, `phase`, `is_fallback`, `resolution_status`, `context_size`, `max_output_tokens`, `provider`, `thinking_enable`, `thinking_capable`, `reasoning_effort`, and `thinking_only`.
- Map `context_size` to `model.context_window_tokens`.
- Use `null` for unavailable token measurements; never synthesize zero or a remaining-token calculation.
- Read `device_type` and `display_hint` from injected context and label them `client_reported`.
- Build the user summary only from the current context’s safe identity fields and never serialize `user_dimensions` wholesale.
- Resolve paths through `resolve_workspace_root(ensure_exists=False)`, `resolve_workspace_user_key`, `resolve_session_workdir`, and `resolve_user_docs_dir`; derive `uploads` and `sandbox` under the same user root, and only report filesystem state without creating directories.
- Report attachment counts and filenames only.
- Include fixed limitation messages for client-reported device data, last-measured token data, and unavailable current estimates.
- Catch path/stat lookup failures per field and return `exists=false`, `writable=false`, and a `path_error` limitation rather than failing the whole tool.

- [ ] **Step 2: Run the focused tests and verify GREEN**

Run:

```bash
pytest --confcutdir=tests/frontend tests/ai/tools/test_session_status.py -q
```

Expected: PASS.

### Task 3: Register the tool and classify its runtime permissions/evidence

**Files:**
- Modify: `app/services/ai/tools/registry.py:1-45,90-120,239-295,804-822`
- Modify: `app/services/ai/runtime/agentscope/tools.py:37-62`
- Modify: `tests/ai/executors/test_system_tools_injection.py:15-75`
- Test: `tests/ai/runtime/test_agentscope_tool_evidence.py` or a focused new assertion in `tests/ai/tools/test_session_status.py`

- [ ] **Step 1: Register the static and implicit tool**

Import `session_status`, add it to `ToolRegistry._registry`, add it to `SYSTEM_IMPLICIT_TOOLS` through `get_system_implicit_tools()`, and keep the tool name unique.

- [ ] **Step 2: Mark it read-only and runtime-state backed**

Add `session_status` to `READ_ONLY_TOOL_NAMES` and map it in `TOOL_EVIDENCE_TYPES` to `frozenset({EvidenceType.RUNTIME_STATE})`. Do not add any mutation permission or user-provided identifier handling.

- [ ] **Step 3: Run registry and runtime contract tests**

Run:

```bash
pytest --confcutdir=tests/frontend tests/ai/tools/test_session_status.py tests/ai/executors/test_system_tools_injection.py tests/ai/runtime/test_agentscope_tool_evidence.py -q
```

Expected: PASS.

### Task 4: Verify repository-scoped quality and hand off

**Files:**
- Review: `docs/superpowers/specs/2026-08-15-session-status-tool-design.md`
- Review: `docs/superpowers/plans/2026-08-15-session-status-tool.md`

- [ ] **Step 1: Run the directly affected AI tool tests**

Run:

```bash
pytest --confcutdir=tests/frontend tests/ai/tools tests/ai/executors/test_system_tools_injection.py tests/ai/runtime/test_agentscope_tool_evidence.py -q
```

Expected: all selected tests pass; unrelated baseline failures must be reported separately.

- [ ] **Step 2: Check the scoped diff**

Run:

```bash
git diff --check -- app/services/ai/tools/session_status.py app/services/ai/tools/registry.py app/services/ai/runtime/agentscope/tools.py tests/ai/tools/test_session_status.py tests/ai/executors/test_system_tools_injection.py docs/superpowers/specs/2026-08-15-session-status-tool-design.md docs/superpowers/plans/2026-08-15-session-status-tool.md
```

Expected: no whitespace errors.

- [ ] **Step 3: Report implementation and verification**

State explicitly that the tool is read-only and current-session scoped, list the tests run, note that no service was started and no commit was created, and identify any unavailable runtime fields as `null` rather than claiming full coverage.
