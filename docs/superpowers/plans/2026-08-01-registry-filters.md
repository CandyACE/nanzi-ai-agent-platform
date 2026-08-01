# Registry Filters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add consistent client-side filtering controls to the model and API tool registries.

**Architecture:** Keep the existing list API calls and action handlers unchanged. Each Vue component will derive a filtered list from its already-loaded data using reactive keyword and select filters, then render that computed list and show a clear empty-result state.

**Tech Stack:** Vue 3 `<script setup>`, TypeScript, existing Tailwind utility classes, existing model/tool API types.

---

### Task 1: Add model registry filters

**Files:**
- Modify: `frontend/src/components/system/ModelRegistry.vue`

- [x] **Step 1: Add reactive filter state and a computed filtered list**

Add keyword, provider, type, and status refs. Match keyword against display name and `model_id`, then filter provider/type/status. Use `filteredModels` for rendering.

- [x] **Step 2: Add the header filter controls**

Place a compact keyword input and three selects between the title and “添加模型” button. Include “全部” options and a clear button shown only when filters are active.

- [x] **Step 3: Render filtered results and empty states**

Change the table loop and empty-state condition from `models` to `filteredModels`. Distinguish “暂无匹配模型” from an actually empty registry.

### Task 2: Add API tool registry filters

**Files:**
- Modify: `frontend/src/components/system/ToolRegistry.vue`

- [x] **Step 1: Add reactive filter state and a computed filtered list**

Match keyword against tool name, description, and URL template; filter by HTTP method and active status.

- [x] **Step 2: Add the header filter controls**

Place the keyword input and method/status selects in the title bar, with a clear button when any filter is active.

- [x] **Step 3: Render filtered results and empty states**

Use `filteredTools` for the table and display “暂无匹配工具” when filters remove all rows.

### Task 3: Validate the UI changes

**Files:**
- Test: `frontend/src/components/system/ModelRegistry.vue`
- Test: `frontend/src/components/system/ToolRegistry.vue`

- [x] **Step 1: Run Vue type checking and confirm no errors point to either registry**

Run `npm exec vue-tsc -- --noEmit` from `frontend/`, then inspect output for the two changed components.

- [x] **Step 2: Run the Vite production bundle**

Run `node --max-old-space-size=4096 ./node_modules/vite/bin/vite.js build` from `frontend/`. Expected result is a successful build; existing chunk-size warnings are acceptable.

- [x] **Step 3: Check the final diff**

Run `git diff --check` and confirm only the two registry components and this plan were changed.
