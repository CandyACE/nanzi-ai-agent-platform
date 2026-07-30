# Dangerous Shell Deletion Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use inline execution with TDD; execute each task in order and keep the worktree changes user-controlled.

**Goal:** Hard-deny deletion of protected global/system roots while requiring explicit confirmation for all other shell deletion operations across NanZi's AgentScope and legacy command paths.

**Architecture:** Add a pure, dependency-light deletion classifier that returns `PASS`, `ASK`, or `DENY`. The AgentScope runtime wrappers call it before generic approval-mode allow handling; the legacy `exec_command` calls it before spawning a subprocess and fails closed for unwrapped deletion requests. Existing non-deletion high-risk checks and user/role command blacklists remain in place.

**Tech Stack:** Python 3.11+, `shlex`, `pathlib`/`os.path`, AgentScope permission decisions, pytest.

> Validation note: the focused policy and boundary tests were run successfully, then the test-only files were removed before commit at the user's request. The production guard remains in place.

---

### Task 1: Add the deletion policy contract and failing unit tests

**Files:**
- Create: `app/services/ai/runtime/shell_deletion_policy.py`
- Test: `tests/ai/runtime/test_shell_deletion_policy.py`

- [x] **Step 1: Write failing policy tests**

  Cover these exact behaviors:

  ```python
  @pytest.mark.parametrize("command", [
      "rm -rf /",
      "rm -rf /*",
      "rm -rf /etc",
      "rm -rf /etc/*",
      "rm -rf /app/data",
      "rm -rf /app/data/*",
      "rm -rf .",
      "rm -rf *",
  ])
  def test_protected_roots_are_hard_denied(command):
      decision = assess_shell_deletion(command, cwd="/app")
      assert decision.action == "deny"

  @pytest.mark.parametrize("command", [
      "rm -rf /tmp/test-dir",
      "rm data/uploads/example.txt",
      "rmdir ./cache",
      "find ./cache -delete",
      "git clean -fd",
  ])
  def test_non_root_deletions_require_confirmation(command):
      decision = assess_shell_deletion(command, cwd="/app")
      assert decision.action == "ask"

  def test_non_delete_commands_pass():
      assert assess_shell_deletion("git status", cwd="/app").action == "pass"

  def test_dynamic_delete_commands_require_confirmation():
      decision = assess_shell_deletion("rm -rf $(pwd)", cwd="/app")
      assert decision.action == "ask"
  ```

  Add cases for `sudo /bin/rm`, compound commands containing a protected deletion, `..` normalization, quoted targets, and unknown shell variables. Keep all tests marked `no_infrastructure` and do not execute any command.

- [x] **Step 2: Run the policy tests and verify the expected RED state**

  Run:

  ```bash
  .venv/bin/python -m pytest tests/ai/runtime/test_shell_deletion_policy.py -q
  ```

  Expected: collection/import failure because `shell_deletion_policy.py` does not exist yet. Fix only test syntax or import mistakes if needed; do not implement production behavior before the failure demonstrates the missing policy.

### Task 2: Implement the pure deletion classifier

**Files:**
- Modify: `app/services/ai/runtime/shell_deletion_policy.py`
- Test: `tests/ai/runtime/test_shell_deletion_policy.py`

- [x] **Step 1: Define the small public contract**

  Add a frozen result type with `action: Literal["pass", "ask", "deny"]`, `reason: str`, and `targets: tuple[str, ...]`. Expose:

  ```python
  def assess_shell_deletion(
      command: str,
      *,
      cwd: str | os.PathLike[str] | None = None,
      protected_roots: Iterable[str] = (),
  ) -> ShellDeletionDecision:
      ...
  ```

- [x] **Step 2: Implement command recognition and conservative parsing**

  Tokenize shell words with `shlex` and treat command separators/control syntax as separate boundaries. Recognize `rm`, `rmdir`, `unlink`, `shred`, `find ... -delete`, and `git clean`. Handle absolute command paths and common wrappers such as `sudo`, `env`, and `command`. If shell parsing fails or dynamic constructs (`$()`, backticks, control-flow blocks, `bash -c`) make the target uncertain, return `ASK` whenever a deletion operation is present.

- [x] **Step 3: Implement protected-root normalization**

  Normalize targets with `expanduser`, `abspath`, and `realpath` without requiring the target to exist. Protect `/`, the Unix system-root list, `~`/`$HOME`, `/app`, `/app/data`, configured skills/data roots, the supplied `cwd`, and supplied protected roots. Treat the protected root itself and full-content wildcards such as `root/*` as `DENY`; descendants such as `/tmp/test-dir` remain `ASK`.

- [x] **Step 4: Run the policy tests and verify GREEN**

  Run the same focused pytest command. Expected: all new classifier tests pass. Then run `git diff --check`.

### Task 3: Gate AgentScope runtime wrappers before `approval_mode=allow`

**Files:**
- Modify: `app/services/ai/runtime/agentscope/tools.py`
- Test: `tests/ai/runtime/test_agentscope_tooling.py`

- [x] **Step 1: Add failing wrapper tests**

  Add tests that monkeypatch the native tool call and assert:

  - `AgentScopeNativeApprovalTool(Bash(), approval_mode="allow").check_permissions({"command": "rm -rf /"}, None)` returns `DENY` with `bypass_immune=True`.
  - The same wrapper with `rm -rf /tmp/test-dir` returns `ASK` with `bypass_immune=True` even under `approval_mode="allow"`.
  - `git status` preserves the current allow behavior.
  - A user forbidden-command decision still remains a hard `DENY`.

  Add the equivalent `AgentScopeRuntimeTool` test for a legacy `exec_command` spec if that wrapper path remains available.

- [x] **Step 2: Run only the new wrapper tests and verify RED**

  Run:

  ```bash
  .venv/bin/python -m pytest tests/ai/runtime/test_agentscope_tooling.py -k 'deletion or allow_mode' -q
  ```

  Expected: the new deletion tests fail because the current wrapper reaches `approval_mode=allow` before deletion safety.

- [x] **Step 3: Add the wrapper helper and enforce ordering**

  Add a small internal helper that maps the classifier result into AgentScope `PermissionDecision` objects. In both wrapper `check_permissions` methods:

  1. Return hard `DENY` for classifier `deny`.
  2. Run existing forbidden-tool and user command blacklist checks so configured policy remains authoritative.
  3. Return bypass-immune `ASK` for classifier `ask`.
  4. Only then evaluate read/dangerous scope, approval mode, and native permission checks.

  Use the native tool's `_cwd` when available and fall back to `os.getcwd()` so relative `.` and `*` are evaluated against the executing workspace.

- [x] **Step 4: Run the wrapper tests and the existing runtime permission slice**

  Run:

  ```bash
  .venv/bin/python -m pytest tests/ai/runtime/test_agentscope_tooling.py -q
  ```

  Expected: all runtime tooling tests pass, including existing native wrapping, alias, blacklist, and fail-closed tests.

### Task 4: Protect the legacy `exec_command` subprocess boundary

**Files:**
- Modify: `app/services/ai/tools/system_executive_tools.py`
- Create: `tests/ai/test_shell_deletion_execution_guard.py`

- [x] **Step 1: Add failing direct-entry tests**

  Add isolated tests that monkeypatch `asyncio.create_subprocess_shell` and assert:

  - `rm -rf /` returns a security-intercept message and the subprocess factory is not called.
  - `rm -rf /tmp/test-dir` returns a confirmation-required message and the subprocess factory is not called when invoked outside the AgentScope permission wrapper.
  - no test creates, overwrites, or removes a real file on the host or in `data/`.

- [x] **Step 2: Run the direct-entry tests and verify RED**

  Run:

  ```bash
  .venv/bin/python -m pytest tests/ai/test_shell_deletion_execution_guard.py -q
  ```

  Expected: the new ordinary-deletion test fails because the legacy function currently launches the shell directly.

- [x] **Step 3: Call the shared classifier before subprocess creation**

  In `exec_command`, evaluate the policy using `cwd=os.getcwd()`. Return a hard security-intercept message for `DENY`. Return a confirmation-required message for `ASK` because this legacy direct function has no confirmation context. Keep the existing `_is_forbidden_shell_command` check for non-deletion high-risk commands and preserve the 30-second timeout/output limits.

- [x] **Step 4: Run the direct-entry tests and full focused regression**

  Run:

  ```bash
  .venv/bin/python -m pytest tests/ai/test_shell_deletion_execution_guard.py -q
  ```

  Expected: all direct executive-tool tests pass without executing any destructive command.

### Task 5: Final verification and handoff

**Files:**
- Modify: only files already listed above if test-driven cleanup is required.

- [x] **Step 1: Run the combined focused security tests**

  ```bash
  .venv/bin/python -m pytest \
    tests/ai/runtime/test_shell_deletion_policy.py \
    tests/ai/runtime/test_agentscope_tooling.py \
    tests/ai/test_shell_deletion_execution_guard.py -q
  ```

- [x] **Step 2: Run static checks**

  ```bash
  git diff --check
  .venv/bin/python -m compileall -q app/services/ai/runtime/shell_deletion_policy.py app/services/ai/runtime/agentscope/tools.py app/services/ai/tools/system_executive_tools.py
  ```

- [x] **Step 3: Inspect the final diff and report boundaries**

  Confirm no service, deployment script, `./dev.sh`, or real deletion command was run. Report focused green proof separately from any unrelated baseline failures. Leave code unstaged and uncommitted for user-controlled finalization.
