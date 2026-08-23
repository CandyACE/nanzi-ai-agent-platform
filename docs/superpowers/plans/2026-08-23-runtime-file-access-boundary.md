# Runtime File Access Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make AgentScope host-backed file tools enforce the normal-user boundary of public roots plus the current user's workspace for reads, and current-user workspace only for writes.

**Architecture:** Keep Docker Bash isolated to the sandbox container. Add a host file-tool authorization wrapper at `bind_configured_tools_to_workspace`, after Docker logical-path translation and before the native AgentScope tool executes. Reuse `app.utils.fs_access` as the single source of public/private path policy and pass the authenticated `user_info` from both assistant runners.

**Tech Stack:** Python 3.11-compatible code, FastAPI/AgentScope native workspace tools, pytest, `realpath`/`commonpath` path checks.

---

### Task 1: Lock the host file-tool authorization contract with failing tests

**Files:**
- Modify: `tests/ai/runtime/test_agentscope_workspace.py`
- Modify: `tests/ai/runtime/test_agentscope_tooling.py` only if the permission decision contract needs a focused regression

- [x] **Step 1: Add read-boundary tests**

  Cover a normal user's `Read`, `Glob`, and `Grep` attempts against their own workspace, a public root, another user's workspace, and an unrelated data directory. Assert allowed calls reach the native tool and denied calls do not.

- [x] **Step 2: Add write-boundary tests**

  Cover `Write` and `Edit` against the current user's workspace, a public root, and another user's workspace. Assert only the private-root call reaches the native tool.

- [x] **Step 3: Add Docker logical-path tests**

  Assert `/workspace/...` is authorized after mapping to the current user's physical root, while `/app/data/agent_workspaces/bob__2/...` is denied.

- [x] **Step 4: Run the focused tests and verify RED**

  Run `venv/bin/python -m pytest tests/ai/runtime/test_agentscope_workspace.py -q` and confirm the new cases fail because native tools currently execute unrestricted absolute paths.

### Task 2: Implement one fail-closed authorization wrapper

**Files:**
- Modify: `app/services/ai/runtime/agentscope/workspace.py`
- Modify: `app/services/ai/runners/assistant_agent_runner.py`
- Modify: `app/services/ai/runners/chatbi/agent_builder.py`

- [x] **Step 1: Add canonical path authorization**

  Implement a wrapper that maps Docker logical inputs, resolves the effective target path, calls `is_path_allowed` for `Read/Glob/Grep`, calls `is_path_writable` for `Write/Edit`, and raises `PermissionError` before native execution when the policy rejects the target.

- [x] **Step 2: Cover omitted search paths**

  Treat a missing `Glob/Grep.path` as the current session/user workspace scope rather than the process working directory.

- [x] **Step 3: Pass authenticated identity into workspace binding**

  Add an optional `user_info` keyword to `bind_configured_tools_to_workspace` and pass the runner's `self.user_info` / `runner.user_info`. Do not weaken authorization when identity is missing.

- [x] **Step 4: Run focused tests and verify GREEN**

  Run the workspace authorization tests and confirm allowed paths execute while denied paths are blocked before the native callable.

### Task 3: Regression verification

**Files:**
- No new production files

- [x] **Step 1: Run related runtime and filesystem tests**

  Run `venv/bin/python -m pytest tests/ai/runtime/test_agentscope_workspace.py tests/ai/runtime/test_agentscope_tooling.py tests/utils/test_fs_access.py tests/ai/test_directory_catalog_tool.py -q`.

- [x] **Step 2: Run static checks on touched files**

  Run the focused Ruff safety subset and `git diff --check`.

- [x] **Step 3: Inspect the final diff and status**

  Confirm only the requested runtime authorization files, tests, and this plan plus the pre-existing catalog changes are present; do not stage or commit.

### Task 4: Allow the two maintained public document links

**Files:**
- Modify: `app/utils/fs_access.py`
- Modify: `tests/utils/test_fs_access.py`
- Modify: `tests/ai/runtime/test_agentscope_workspace.py`

- [x] **Step 1: Add a failing symlink-target regression test**

  Link `data/docs/FAQ.md` and `data/docs/README.md` to the application-root files, and link another public-docs entry to `docker/README.md`. Assert only the two named targets are readable and all writes remain denied.

- [x] **Step 2: Add the exact read-only target allowlist**

  Resolve the application root from `app/utils/fs_access.py`, allow only `FAQ.md` and `README.md` as exact canonical read targets, and leave the writable policy unchanged.

- [x] **Step 3: Verify the runtime and filesystem boundaries**

  Run the focused runtime/filesystem suite, production Ruff checks, Python compilation, and scoped `git diff --check`. Expected result: `95 passed, 1 deselected`; no production Ruff findings.
