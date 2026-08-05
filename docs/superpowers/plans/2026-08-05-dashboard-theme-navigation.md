# Dashboard 主题导航 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persistent light/dark theme switch to the existing Dashboard shell and implement the approved light sidebar navigation.

**Architecture:** Keep the existing `Dashboard.vue` menu groups, permission filtering, routes, collapse behavior, and mobile behavior unchanged. Add a singleton `useAppTheme` composable that owns localStorage persistence and a document theme data attribute; Dashboard consumes that state only for sidebar classes, leaving the header and main content unchanged.

**Tech Stack:** Vue 3, TypeScript, Tailwind CSS 3, pytest frontend contract tests.

---

### Task 1: Lock the theme contract with a failing test

**Files:**
- Create: `tests/frontend/test_dashboard_theme_contract.py`

- [x] Assert the new composable uses the stable storage key, supports `light` and `dark`, and toggles `document.documentElement.classList`.
- [x] Assert Dashboard renders the theme switcher, preserves collapsed accessibility via a title, and contains both light and dark shell classes.
- [x] Run `venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_dashboard_theme_contract.py -q`; it failed before implementation because the composable and switcher did not exist yet.

### Task 2: Add the persistent theme state

**Files:**
- Create: `frontend/src/composables/useAppTheme.ts`
- Modify: `frontend/src/App.vue`

- [x] Implement module-level `theme` state defaulting to `light`, read `nanzi_app_theme` from localStorage when available, and expose `setTheme`/`toggleTheme`.
- [x] Apply the `data-theme` attribute to `document.documentElement` whenever the theme changes, without enabling a global `dark` class, and initialize it once from `App.vue` on mount.
- [x] Run the new contract test; it passed after the composable and Dashboard switcher were implemented.

### Task 3: Implement the approved Dashboard sidebar theme

**Files:**
- Modify: `frontend/src/views/Dashboard.vue`

- [x] Consume `useAppTheme` and expose the current theme to the template.
- [x] Add an expanded segmented “亮色/暗色” control above the user profile and an icon-only control when the sidebar is collapsed.
- [x] Change only shell/sidebar classes: light uses white background, slate text, blue-tinted active item and light borders; dark retains the current navy background and existing active/hover treatment.
- [x] Keep the top header and scrollable main background on their existing light classes so the switch only affects the sidebar.
- [x] Run the new contract test and the existing Dashboard/sidebar contract tests; the focused Dashboard/brand/permission/scenario subset passed, while an unrelated existing saved-report notification assertion failed.

### Task 4: Verify the frontend result

**Files:**
- No additional production files.

- [x] Run `venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_dashboard_theme_contract.py tests/frontend/test_dashboard_sidebar_brand_contract.py -q`.
- [x] Run `./node_modules/.bin/vue-tsc --noEmit` from `frontend/`.
- [x] Run `git diff --check` and inspect `git status --short` to ensure unrelated worktree changes remain untouched.
