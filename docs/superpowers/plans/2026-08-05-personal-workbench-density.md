# Personal Workbench Information Density Implementation Plan

> **For agentic workers:** Implement this plan task-by-task with test-first checkpoints. Do not alter unrelated worktree edits.

**Goal:** Make the existing personal workbench useful and information-dense with real summaries, deduplicated conversations, actionable empty states, and responsive layout.

**Architecture:** Keep `WorkbenchHomeService` as the aggregate boundary. Normalize duplicate conversation records there, keep the existing `WorkbenchHomePayload` shape, and implement copy/layout changes in the existing workbench components without adding fake data or new routes.

**Tech Stack:** FastAPI, SQLAlchemy async, pytest, Vue 3, TypeScript, Tailwind CSS.

---

### Task 1: Normalize duplicate resumable conversations

**Files:**
- Modify: `app/services/workbench_home_service.py`
- Test: `tests/services/test_workbench_home_service.py`

- [x] Add a failing test with two conversation items sharing `target.conversation_id`; expect one item using the newest `occurred_at`.
- [x] Run `venv/bin/python -m pytest tests/services/test_workbench_home_service.py -q` and confirm the duplicate remains.
- [x] Add a helper at the payload normalization boundary that keeps the newest item per conversation target and preserves non-conversation items.
- [x] Run the focused service test and confirm it passes.

### Task 2: Make summary text reflect actionable state

**Files:**
- Modify: `frontend/src/views/PersonalWorkbench.vue`
- Test: `tests/frontend/test_personal_workbench_contract.py`

- [x] Add contract assertions for “可继续” and “最近没有新的产出” copy and the quiet-state count path.
- [x] Update computed summary text so resumable work takes precedence over the generic “今日运行正常” message.
- [x] Keep active/new-user modes and existing route actions unchanged.
- [x] Run `venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_personal_workbench_contract.py -q`.

### Task 3: Improve empty output and compact layout

**Files:**
- Modify: `frontend/src/components/workbench/WorkbenchResults.vue`
- Modify: `frontend/src/views/PersonalWorkbench.vue`
- Test: `tests/frontend/test_personal_workbench_contract.py`

- [x] Add assertions for the data-portal empty-state CTA and the responsive two-column layout.
- [x] Change empty output copy to a direct “创建第一份报表” action while preserving the existing `openReports` route.
- [x] Use a compact grid for resume/results on wide screens and keep one-column stacking on narrow screens.
- [x] Run the frontend contract test and `git diff --check`.

### Task 4: Final focused verification

**Files:**
- No additional production files.

- [x] Run `venv/bin/python -m pytest tests/services/test_workbench_home_service.py tests/api/portal/test_workbench_home_api.py -q`.
- [x] Run `venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_personal_workbench_contract.py -q`.
- [x] Run `venv/bin/python -m py_compile app/services/workbench_home_service.py`.
- [x] Inspect `git status --short` and confirm unrelated worktree modifications remain untouched.
