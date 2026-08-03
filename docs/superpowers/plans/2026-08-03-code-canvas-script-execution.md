# Code Canvas Script Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add confirmed, streamed, stoppable execution for AI-generated Python and Shell code blocks inside the existing ChatCanvas.

**Architecture:** Add a shared controlled process executor for the existing shell tool and the new code-execution API, then expose an authenticated SSE endpoint plus an execution-specific stop endpoint. Extend the existing `MessageRenderer` → `ChatCanvas` payload with runnable language metadata and keep execution state in a shared `useCodeExecution` composable so EmbedChat and AgentDebug retain identical behavior.

**Tech Stack:** FastAPI, Pydantic, asyncio subprocess process groups, SSE `StreamingResponse`, Vue 3 `<script setup>`, TypeScript, Axios/fetch streaming, pytest contract tests.

---

## File map

- Create `app/services/ai/code_execution_service.py`: language normalization, session-scoped script materialization, process-group execution, output limits, timeout, stop registry, and shared shell-policy calls.
- Modify `app/services/ai/tools/system_executive_tools.py`: delegate the existing `exec_command` process execution to the shared service while preserving its current string result contract and 30-second tool timeout behavior.
- Create `app/api/v1/endpoints/code_execution.py`: authenticated `POST .../stream` and `POST .../{execution_id}/stop` endpoints plus request/event models.
- Modify `app/api/v1/api.py`: mount the new router under the secured V1 API.
- Modify `frontend/src/components/MessageRenderer.vue`: carry `langName`/runnable metadata into the canvas event and show the runnable card action only for supported script languages.
- Create `frontend/src/composables/chat/useCodeExecution.ts`: one frontend execution state machine, SSE parsing, stop handling, cleanup, and output accumulation.
- Modify `frontend/src/components/embed/ChatCanvas.vue`: render the run/stop/confirm controls and stacked code/output layout without adding workspace-file execution.
- Create `tests/services/ai/test_code_execution_service.py`: pure language/policy/process lifecycle tests.
- Create `tests/api/v1/test_code_execution.py`: request authorization, SSE events, stop ownership, and validation tests.
- Modify `tests/test_system_executive_tools.py`: preserve existing `exec_command` behavior through the shared service.
- Create `tests/frontend/test_code_execution_contract.py`: source-level contracts for runnable metadata, shared composable use, UI states, and workspace-file exclusion.
- Modify `tests/frontend/test_message_renderer_contract.py`: regression coverage for Python/Shell runnable cards and non-runnable languages.

## Task 1: Lock the backend service contract with failing tests

**Files:**
- Create: `tests/services/ai/test_code_execution_service.py`
- Create: `app/services/ai/code_execution_service.py` only after the failing tests are verified

- [ ] **Step 1: Write failing normalization and command-building tests**

Add tests that define the public service contract:

```python
def test_normalize_language_accepts_python_and_shell_aliases():
    assert normalize_language("python3") == "python"
    assert normalize_language("bash") == "bash"
    assert normalize_language("shell") == "bash"


def test_normalize_language_rejects_unrunnable_language():
    with pytest.raises(CodeExecutionValidationError, match="暂不支持"):
        normalize_language("javascript")


def test_build_script_command_uses_fixed_interpreters_and_unbuffered_python(tmp_path):
    assert build_script_command("python", tmp_path / "run.py") == [
        sys.executable, "-u", str(tmp_path / "run.py")
    ]
    assert build_script_command("sh", tmp_path / "run.sh")[0:2] == ["/bin/sh", str(tmp_path / "run.sh")]
```

Import the planned names from `app.services.ai.code_execution_service`; do not use mocks for these pure functions.

- [ ] **Step 2: Run the new tests and verify the expected failure**

Run:

```bash
venv/bin/python -m pytest tests/services/ai/test_code_execution_service.py -q
```

Expected: collection fails because `app.services.ai.code_execution_service` and its public symbols do not exist yet.

- [ ] **Step 3: Implement only the normalization and command builder**

Define:

```python
SUPPORTED_LANGUAGES = frozenset({"python", "python3", "shell", "sh", "bash"})

def normalize_language(value: str) -> Literal["python", "sh", "bash"]:
    # lowercase and strip; map python3 -> python and shell -> bash;
    # raise CodeExecutionValidationError for all other values.

def build_script_command(language: str, script_path: Path) -> list[str]:
    # return [sys.executable, "-u", path] for Python;
    # return ["/bin/sh", path] for sh;
    # return ["/bin/bash", path] for bash.
```

Do not accept an interpreter path, cwd, extra argv, or environment values from the request.

- [ ] **Step 4: Run the focused tests and verify they pass**

Run the same pytest command. Expected: all normalization and command-builder tests pass.

## Task 2: Add failing tests for safety, streaming, timeout, and stop

**Files:**
- Modify: `tests/services/ai/test_code_execution_service.py`

- [ ] **Step 1: Add tests for session-scoped materialization and policy rejection**

Cover these exact cases:

```python
def test_materialize_script_stays_under_session_workspace(tmp_path):
    path = materialize_script(tmp_path, "python", "print('ok')")
    assert path.parent == tmp_path
    assert path.suffix == ".py"
    assert path.read_text() == "print('ok')"


@pytest.mark.asyncio
async def test_shell_policy_rejection_happens_before_process_creation(monkeypatch, tmp_path):
    created = False

    async def fail_if_created(*args, **kwargs):
        nonlocal created
        created = True
        raise AssertionError("process must not start")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fail_if_created)
    result = await execute_code_stream(
        language="bash", code="rm -rf /", workspace=tmp_path, user_info={"user_id": 1}
    ).collect()
    assert result.status == "blocked"
    assert not created
```

Use the repository's current `assess_shell_deletion` and user/role blacklist checks as the policy dependencies; the test must prove rejection occurs before process creation.

- [ ] **Step 2: Add real subprocess tests for ordered stdout/stderr and exit code**

Use a temporary Python script and the actual subprocess runner:

```python
@pytest.mark.asyncio
async def test_execute_code_stream_emits_ordered_output_and_exit_code(tmp_path):
    result = await execute_code_stream(
        language="python",
        code="import sys\nprint('out', flush=True)\nprint('err', file=sys.stderr, flush=True)\nraise SystemExit(3)",
        workspace=tmp_path,
        user_info={"user_id": 1},
    ).collect()
    assert [(item.stream, item.text) for item in result.outputs] == [
        ("stdout", "out\n"), ("stderr", "err\n")
    ]
    assert result.status == "failed"
    assert result.exit_code == 3
```

- [ ] **Step 3: Add 60-second timeout and process-group stop tests**

Inject a short timeout parameter in the service test API so tests do not sleep for 60 seconds, while production defaults remain 60:

```python
@pytest.mark.asyncio
async def test_timeout_terminates_the_process_group(tmp_path):
    result = await execute_code_stream(
        language="python", code="import time; time.sleep(1)", workspace=tmp_path,
        user_info={"user_id": 1}, timeout_seconds=0.05,
    ).collect()
    assert result.status == "timed_out"


@pytest.mark.asyncio
async def test_stop_is_idempotent_and_reports_stopped(tmp_path):
    handle = start_code_execution(
        language="python", code="import time; time.sleep(10)",
        workspace=tmp_path, user_info={"user_id": 1},
    )
    await handle.started.wait()
    assert await handle.stop() is True
    assert await handle.stop() is False
    assert (await handle.result()).status == "stopped"
```

- [ ] **Step 4: Run the tests and verify they fail for missing execution behavior**

Run:

```bash
venv/bin/python -m pytest tests/services/ai/test_code_execution_service.py -q
```

Expected: the new tests fail because the execution handle, event collection, and process lifecycle are not implemented.

## Task 3: Implement the shared controlled executor

**Files:**
- Modify: `app/services/ai/code_execution_service.py`
- Modify: `app/services/ai/runtime/shell_deletion_policy.py` only if the shared service needs a typed policy adapter; preserve existing behavior

- [ ] **Step 1: Add typed request/event/result models and constants**

Use explicit literals for statuses and streams:

```python
DEFAULT_TIMEOUT_SECONDS = 60.0
MAX_OUTPUT_BYTES = 100 * 1024
ExecutionStatus = Literal["succeeded", "failed", "stopped", "timed_out", "blocked"]
OutputStream = Literal["stdout", "stderr"]
```

Each output event must retain stream, text, and monotonic sequence number. Each execution handle must retain execution ID, owner user ID, conversation ID, process reference, and workspace path.

- [ ] **Step 2: Implement safe script materialization**

Create a random temporary filename directly under the already-resolved session workspace. Select `.py` or `.sh` based on normalized language. Reject a workspace outside the approved session root, reject code above the configured request size, write UTF-8 text, and unlink the file in a `finally` block.

- [ ] **Step 3: Implement policy checks before process creation**

For Shell, call `assess_shell_deletion` and the existing user/role command blacklist logic with the submitted script content/launch command. Return a `blocked` result with a stable reason before starting a process. Do not turn a policy result into a successful process result.

For Python, require the deployment's session/container sandbox and fixed interpreter. Do not claim that Shell token checks make arbitrary Python safe; if the process sandbox feature is disabled, return `blocked` with an explicit configuration message.

- [ ] **Step 4: Implement process-group streaming and cleanup**

Use `asyncio.create_subprocess_exec` with separate stdout/stderr pipes, the resolved session workspace as cwd, and a new process group/session. Read both pipes concurrently, emit chunks in arrival order, enforce the combined 100KB cap, and use `asyncio.wait_for` with the request timeout. On timeout or stop, terminate the process group, wait briefly, then kill it if needed. Always close pipes and unlink the temporary script.

- [ ] **Step 5: Run the service test file and fix only implementation failures**

Run:

```bash
venv/bin/python -m pytest tests/services/ai/test_code_execution_service.py -q
```

Expected: all service lifecycle tests pass. Do not run the full suite yet.

## Task 4: Preserve the existing exec_command contract through the shared service

**Files:**
- Modify: `app/services/ai/tools/system_executive_tools.py`
- Modify: `tests/test_system_executive_tools.py`

- [ ] **Step 1: Add a regression assertion for the existing result envelope**

Keep the existing `exec_command.ainvoke({"command": "echo 'NanZi'"})` test and add assertions that stdout, stderr, exit code, timeout, and dangerous-command messages remain unchanged.

- [ ] **Step 2: Run the regression test before changing production code**

Run:

```bash
venv/bin/python -m pytest tests/test_system_executive_tools.py::test_exec_command -q
```

Expected: current baseline passes; the new shared delegation is not present yet.

- [ ] **Step 3: Delegate only process execution to the shared service**

Keep the existing tool decorator and string response format. Pass the current tool command through the shared timeout/output/process cleanup implementation, while preserving the current 30-second `exec_command` timeout as a tool-specific override. Keep existing policy imports and messages compatible.

- [ ] **Step 4: Run focused backend regressions**

Run:

```bash
venv/bin/python -m pytest tests/services/ai/test_code_execution_service.py tests/test_system_executive_tools.py -q
```

Expected: all shared executor and legacy tool tests pass.

## Task 5: Add the authenticated SSE API with failing API tests first

**Files:**
- Create: `tests/api/v1/test_code_execution.py`
- Create: `app/api/v1/endpoints/code_execution.py` only after RED is verified
- Modify: `app/api/v1/api.py`

- [ ] **Step 1: Write API tests for validation and ownership**

Cover invalid language, missing code, missing/invalid conversation ID, unauthenticated access, and stop requests from a different user. The stream test must assert `content-type: text/event-stream` and decode events named `started`, `output`, and `finished`.

- [ ] **Step 2: Run the API tests and verify RED**

Run:

```bash
venv/bin/python -m pytest tests/api/v1/test_code_execution.py -q
```

Expected: collection or route-not-found failures because the router does not exist.

- [ ] **Step 3: Implement request models, execution registry, and routes**

The stream route must depend on the existing secured V1 router, resolve the authenticated user and session workspace, create an execution handle, and yield JSON-encoded SSE records in the form `event: <name>\ndata: <json>\n\n`. The stop route must look up the execution ID, compare both user ID and conversation ID, and return an idempotent status.

- [ ] **Step 4: Mount the router and run API tests**

Add `v1_secured.include_router(code_execution.router, prefix="/chat/code-executions", tags=["V1 代码执行"])` in `app/api/v1/api.py`, then run the same test command. Expected: all API tests pass.

## Task 6: Lock the frontend payload and card behavior with failing tests

**Files:**
- Create: `tests/frontend/test_code_execution_contract.py`
- Modify: `tests/frontend/test_message_renderer_contract.py`
- Modify: `frontend/src/components/MessageRenderer.vue` only after RED is verified

- [ ] **Step 1: Add source contracts for language metadata and runnable gating**

Assert that the canvas payload carries `langName`, that the supported-language set is explicit, that `canvas_html` remains an HTML-only action, and that unsupported long code still uses “查看代码” without “运行”.

- [ ] **Step 2: Run the frontend contract tests and verify RED**

Run:

```bash
venv/bin/python -m pytest tests/frontend/test_code_execution_contract.py tests/frontend/test_message_renderer_contract.py -q
```

Expected: the new assertions fail because the current canvas payload has no runnable metadata or language gate.

- [ ] **Step 3: Add runnable metadata to MessageRenderer**

Use a single constant such as `RUNNABLE_CODE_LANGUAGES = new Set(['python', 'python3', 'shell', 'sh', 'bash'])`. Preserve the existing `>15` line threshold. For supported languages, emit `runnable: true` and the normalized language; for other languages emit `runnable: false`. The card action should be “运行” when runnable and retain “查看代码” otherwise.

- [ ] **Step 4: Run the frontend contracts**

Run the same pytest command. Expected: all payload and card tests pass.

## Task 7: Add the shared frontend execution composable

**Files:**
- Create: `frontend/src/composables/chat/useCodeExecution.ts`
- Modify: `tests/frontend/test_code_execution_contract.py`

- [ ] **Step 1: Add failing composable behavior tests**

Cover initial `idle`, `confirming`, `running`, `succeeded`, `failed`, `stopped`, `timed_out`, and `blocked` states; output ordering; cancellation; and cleanup on stop. The test harness must feed deterministic SSE strings to a parser rather than requiring a live server.

- [ ] **Step 2: Run the focused frontend behavior test and verify RED**

Run:

```bash
venv/bin/python -m pytest tests/frontend/test_code_execution_contract.py -q
```

Expected: the new composable/parser contracts fail because the module does not exist.

- [ ] **Step 3: Implement `useCodeExecution`**

Expose:

```ts
type CodeExecutionState =
  | 'idle' | 'confirming' | 'starting' | 'running'
  | 'succeeded' | 'failed' | 'stopped' | 'timed_out' | 'blocked';

useCodeExecution({ conversationId, language, code }): {
  state, outputs, exitCode, elapsedMs, errorMessage,
  requestRun, confirmRun, cancelConfirmation, stop, clearOutput,
}
```

Use `fetch` with the existing authenticated Axios/base URL conventions, parse SSE records from `ReadableStream.getReader()`, append output by sequence, and use `AbortController` only for the client stream; call the stop endpoint before aborting when an execution ID exists.

- [ ] **Step 4: Run frontend parser/composable tests**

Run the same focused pytest command and then the existing `tests/frontend/test_chat_shared_helpers_behavior.py` slice. Expected: all pass.

## Task 8: Integrate the run UI into ChatCanvas and both chat surfaces

**Files:**
- Modify: `frontend/src/components/embed/ChatCanvas.vue`
- Modify: `frontend/src/components/MessageRenderer.vue` if event payload typing needs alignment
- Modify: `frontend/src/views/EmbedChat.vue` only if the shared canvas payload needs conversation ID forwarding
- Modify: `frontend/src/views/AgentDebug.vue` only if the shared canvas payload needs conversation ID forwarding
- Modify: `tests/frontend/test_code_execution_contract.py`

- [ ] **Step 1: Add failing UI contracts**

Assert that `ChatCanvas` renders a confirmation step, code-above-output layout, run/stop labels, live stdout/stderr styling, and does not render run controls when `sourcePath` is present. Assert both chat views pass the current conversation ID into `ChatCanvas`.

- [ ] **Step 2: Run the UI contracts and verify RED**

Run:

```bash
venv/bin/python -m pytest tests/frontend/test_code_execution_contract.py -q
```

Expected: the new UI assertions fail against the current display-only canvas.

- [ ] **Step 3: Implement the minimal Canvas UI**

Add the run button beside copy/download for runnable direct code, an inline confirmation dialog with cancel/confirm actions, an output panel below the existing code panel, a stop button during execution, and terminal status text for success/failure/stopped/timeout/blocked. Do not add execution controls to workspace-file previews.

- [ ] **Step 4: Run frontend SFC/contracts and type checks**

Run:

```bash
venv/bin/python -m pytest tests/frontend/test_code_execution_contract.py tests/frontend/test_message_renderer_contract.py tests/frontend/test_chat_canvas_resizer_contract.py -q
cd frontend && ./node_modules/.bin/vue-tsc --noEmit
```

Expected: focused tests pass; `vue-tsc` either passes or reports only pre-existing unrelated baseline errors, which must be recorded separately.

## Task 9: Full focused verification and handoff

**Files:**
- Modify: no production files unless a test exposes a defect

- [ ] **Step 1: Run all feature tests**

```bash
venv/bin/python -m pytest \
  tests/services/ai/test_code_execution_service.py \
  tests/api/v1/test_code_execution.py \
  tests/test_system_executive_tools.py \
  tests/frontend/test_code_execution_contract.py \
  tests/frontend/test_message_renderer_contract.py \
  tests/frontend/test_chat_canvas_resizer_contract.py -q
```

- [ ] **Step 2: Run static checks**

```bash
git diff --check
PYTHONPATH=. venv/bin/python -m py_compile \
  app/services/ai/code_execution_service.py \
  app/api/v1/endpoints/code_execution.py
```

- [ ] **Step 3: Inspect the final diff and unrelated worktree changes**

Use `git status --short` and `git diff --stat`; do not stage or modify the existing unrelated changes in `app/services/ai/runtime/agentscope/confirmations.py`, `app/services/ai/runtime/agentscope/serialize.py`, or `tests/ai/runtime/test_agentscope_state_pending.py`.

- [ ] **Step 4: Hand off for manual runtime acceptance**

Tell the user to start the application manually with `./dev.sh` and validate, in an authenticated browser: Python success/failure, Shell pipeline, confirmation cancel, stop, timeout, blocked command, and both EmbedChat/AgentDebug. Do not run `./dev.sh` from the agent.

## Plan self-review

- Spec coverage: scope, 60-second timeout, confirmation, real-time stdout/stderr, stacked layout, stop, SSE, ownership, shared safety, process groups, output limits, workspace exclusion, frontend/backend tests, and manual acceptance are covered in Tasks 1–9.
- Placeholder scan: every task names concrete files, symbols, commands, and expected outcomes.
- Type consistency: the service uses normalized `python`/`sh`/`bash`; frontend payload carries normalized `langName`; API events use `execution_id`, `stream`, `chunk`, `status`, `exit_code`, and `elapsed_ms` consistently.
