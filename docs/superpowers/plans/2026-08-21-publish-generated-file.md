# Publish Generated File Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an implicitly registered built-in tool that publishes an existing current-user workspace file and returns a real tokenized download URL.

**Architecture:** Keep file creation and artifact publication separate. The new tool resolves local, session-relative, and Docker `/workspace` paths into the current user's workspace, delegates persistence and token creation to `register_artifact`, and returns a structured payload containing the download URL and expiry. `ToolRegistry.get_system_implicit_tools()` exposes it to Assistant, Knowledge, and ChatBI runtimes without per-agent configuration.

**Tech Stack:** Python 3.11, AgentScope runtime tool registry, FastAPI download route, SQLAlchemy `ai_artifacts` persistence, pytest.

---

### Task 1: Define the publish tool contract with failing tests

**Files:**
- Create: `tests/ai/tools/test_generated_file_tool.py`
- Modify: `app/services/ai/tools/registry.py`

- [x] **Step 1: Write tests for successful publication, path normalization, and implicit registration**

  Test a Markdown file under the current user's docs directory, a Docker-style `/workspace/docs/...` path, rejection of another user's workspace, and presence in `ToolRegistry.get_system_implicit_tools()`.

- [x] **Step 2: Run the focused tests and verify they fail because the tool is missing**

  Run: `PYTHONPATH=. venv/bin/python -m pytest tests/ai/tools/test_generated_file_tool.py -q`

  Expected: collection/import or assertion failures indicating `publish_generated_file` is not registered.

### Task 2: Implement the path-safe publishing tool

**Files:**
- Create: `app/services/ai/tools/generated_file_tool.py`
- Modify: `app/services/ai/tools/registry.py`

- [x] **Step 1: Resolve the current context and supported path forms**

  Accept `path`, optional `filename`, and optional `artifact_type`; resolve relative paths from the current session workdir, translate `/workspace/...` to the current user's workspace root, and accept absolute paths only when they remain under that user's workspace.

- [x] **Step 2: Publish through `register_artifact` and return a structured payload**

  Return `status`, `summary`, `filename`, `mime_type`, `size`, `download_url`, and `expires_at`. Never expose a physical path as the download address. Convert missing context, missing files, cross-user paths, expired/invalid paths, and registration failures into actionable tool errors.

- [x] **Step 3: Register the tool as an implicit system tool**

  Add it to the registry and the list returned by `ToolRegistry.get_system_implicit_tools()`. Keep the runtime permission scope as `ask` because publication creates a persistent capability link.

- [x] **Step 4: Re-run the focused tests and verify they pass**

  Run: `PYTHONPATH=. venv/bin/python -m pytest tests/ai/tools/test_generated_file_tool.py -q`

  Expected: all focused tests pass.

### Task 3: Regression verification

**Files:**
- Test only: existing generated-file, registry, Word, Excel, and runtime tool tests.

- [x] **Step 1: Run the focused artifact and registry suite**

  Run: `PYTHONPATH=. venv/bin/python -m pytest tests/ai/tools/test_generated_file_tool.py tests/ai/tools/test_generated_file_service.py tests/ai/tools/test_registry.py tests/ai/tools/test_word_document_tool.py tests/ai/tools/test_excel_document_tool.py tests/api/v1/test_generated_file_download.py tests/api/v1/test_chat_artifacts.py -q`

- [x] **Step 2: Check formatting and diff integrity**

  Run: `git diff --check`

- [x] **Step 3: Report the changed files and test results without staging or committing**

### Task 4: Add the model-facing delivery contract

- [x] Add a dynamic platform prompt rule requiring `publish_generated_file` after file generation and requiring a successful `download_url` before claiming delivery.
- [x] Add a prompt regression test covering the rule.

### Task 5: Use the configured public origin in download URLs

- [x] Centralize download URL construction through `APP_PUBLIC_URL` with a relative-path fallback when the setting is empty.
- [x] Apply the same URL construction to the artifact list endpoint and update document-tool instructions.
- [x] Add configured-origin regression coverage and rerun the artifact, tool-injection, and Thinking compatibility suites.

### Task 6: Move the download prefix into General Settings

- [x] Seed `download_url_prefix` in the MySQL and PostgreSQL migration chains under the `general` category.
- [x] Prefer the persisted system setting at runtime, with `APP_PUBLIC_URL` retained as a compatibility fallback.
- [x] Add the General Settings input, ordering, and inline setup example.
- [x] Verify the system-config contract and frontend type checking.

### Task 7: Extend the default download-link lifetime

- [x] Change the shared `DEFAULT_TTL` from 24 hours to 7 days.
- [x] Add a regression test covering the one-week default.
