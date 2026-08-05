# Personal Workbench Running Items Implementation Plan

> **For agentic workers:** Implement this plan task-by-task with test-first checkpoints. Do not alter unrelated worktree edits.

**Goal:** Extend the personal workbench with a persistent `running_items` section backed by real saved-report runs, while preserving the existing attention/resume/result workflow.

**Architecture:** Keep `WorkbenchHomeService` as the single aggregation boundary. Add a source loader for persistent saved-report executions, normalize it into the existing `WorkbenchItem` shape, then render a dedicated `WorkbenchRunning` component. Session-level AgentScope confirmations remain inside the active chat stream and are not promoted to the workbench.

**Tech Stack:** FastAPI, SQLAlchemy async, Redis async scan, pytest contract tests, Vue 3, TypeScript, Vite.

---

### Task 1: Add failing aggregation tests

**Files:**
- Modify: `tests/services/test_workbench_home_service.py`
- Modify: `tests/frontend/test_personal_workbench_contract.py`

- [x] Add a service test requiring `running_items` to normalize an active saved-report run with source labels, targets, and stable action names.
- [x] Confirm session-level pending snapshots are excluded from the workbench boundary.
- [x] Add frontend contract assertions for the running section, source labels, and target action handling.
- [x] Run the focused tests and verify they fail because `running_items` and the new component do not exist yet.

### Task 2: Implement source loaders and API contract

**Files:**
- Modify: `app/services/workbench_home_service.py`

- [x] Query current-user `PortalSavedReportRun` rows with status `running`, limited and ordered by `started_at`.
- [x] Normalize saved-report runs into `running_items` without inventing progress percentages.
- [x] Keep source failures isolated through the existing `_safe_load` pattern and add `running` to source status.

### Task 3: Implement the workbench UI

**Files:**
- Create: `frontend/src/components/workbench/WorkbenchRunning.vue`
- Modify: `frontend/src/types/workbench.ts`
- Modify: `frontend/src/views/PersonalWorkbench.vue`
- Modify: `frontend/src/utils/workbenchDisplay.ts` if new actions need labels

- [x] Render running saved-report items with explicit source/status labels.
- [x] Link saved-report items to the existing data-portal report/run route.
- [x] Show the section only when real items exist; preserve active/quiet/new-user behavior and existing empty states.
- [x] Keep the layout responsive and use the existing workbench visual language.

### Task 4: Verify the focused slice

**Files:**
- No additional production files.

- [x] Run `venv/bin/python -m pytest tests/services/test_workbench_home_service.py tests/api/portal/test_workbench_home_api.py -q`.
- [x] Run `venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_personal_workbench_contract.py -q`.
- [x] Run `git diff --check` and inspect the diff to confirm unrelated worktree changes were preserved.
