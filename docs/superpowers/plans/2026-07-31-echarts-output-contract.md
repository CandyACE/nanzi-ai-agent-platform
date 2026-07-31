# ECharts Output Contract Implementation Plan

> **For agentic workers:** Execute this plan task-by-task with checkpoints. Do not run `./dev.sh`.

**Goal:** Make AI-generated ECharts blocks follow one platform contract and make invalid chart output fail with an actionable reason.

**Architecture:** Keep the existing SSE/Markdown message protocol. Add one reusable platform-wide prompt contract for numeric data-chart producers, narrow the frontend chart fence matcher to chart-specific fences, validate/normalize chart options before rendering, and keep the frontend-supported chart type list aligned with the prompt contract. Mermaid remains available for structural diagrams.

**Tech Stack:** Python prompt builders and pytest; Vue 3/TypeScript; ECharts 5; Node TypeScript contract tests.

---

### Task 1: Define the shared chart output contract

**Files:**
- Modify: `app/services/ai/agent_prompts.py`
- Modify: `app/services/ai/executors/prompts.py`
- Test: `tests/ai/test_data_query_prompts.py`
- Test: `tests/ai/test_prompt_assembler.py`

- [x] Add a platform-wide `AgentServicePrompts.GLOBAL_VISUALIZATION_CONTRACT` and a ChatBI-specific reusable contract covering the `chart` fence, strict JSON, root `series` array, supported types, required cartesian axes, safe data forms, and prohibition of JavaScript functions/comments/extra code-block text.
- [x] Inject the platform-wide contract into the normal global prompt and the separate multi-agent synthesis prompt, so Main Agent and aggregation do not fall back to Mermaid `xychart`.
- [x] Include that constant in normal synthesis, follow-up synthesis, format correction, and federated synthesis prompts.
- [x] Add tests asserting every active ChatBI synthesis builder includes the contract and the key constraints.
- [x] Run the focused prompt tests and confirm the new assertions fail before implementation and pass after implementation.

### Task 2: Add parser validation and actionable errors

**Files:**
- Modify: `frontend/src/utils/chartRenderer.ts`
- Test: `frontend/scripts/chartRenderer.test.ts`

- [x] Add a supported chart type set matching the prompt contract.
- [x] Extend `ChartParseResult` with a stable error code/message suitable for the UI.
- [x] Normalize a single `series` object to an array for legacy compatibility, then validate root shape, series type, and required data/axis structure.
- [x] Convert only the well-known Chart.js-like `type + data.labels + data.datasets` shape into standard ECharts before the same validation; reject other malformed shapes.
- [x] Keep JSON5 parsing only as backward compatibility, while rejecting executable JavaScript values and unsupported chart types.
- [x] Add failing tests for `series` object normalization, formatter functions, unsupported types, missing series, and invalid chart fence content.

### Task 3: Make MessageRenderer classify and report failures correctly

**Files:**
- Modify: `frontend/src/components/MessageRenderer.vue`
- Test: `tests/frontend/test_message_renderer_contract.py`

- [x] Change the chart fence matcher to accept only `chart` and `echarts`, not arbitrary `json` code blocks.
- [x] Pass parser error details into the fallback card while keeping raw JSON available for inspection.
- [x] Preserve the existing chart/table toggle and chart rendering path.
- [x] Add contract assertions for the accepted fences, rejected generic JSON fence, and actionable failure text.

### Task 4: Verify producer/renderer compatibility

**Files:**
- Modify: `frontend/src/components/MessageRenderer.vue` only if registration needs alignment
- Test: `frontend/scripts/chartRenderer.test.ts`, `tests/frontend/test_message_renderer_contract.py`, `tests/ai/test_data_query_prompts.py`

- [x] Verify the prompt-supported chart types equal the types registered in `MessageRenderer.vue`.
- [x] Verify the screenshot-shaped legacy data configuration is converted into an ECharts option with category axis and series data.
- [x] Run the Node chart renderer test.
- [x] Run focused Python prompt/frontend contract tests.
- [x] Run `git diff --check` and report unrelated baseline failures separately if any.

### Task 5: Review the final diff

- [x] Confirm only the chart output contract, parser diagnostics, and focused tests changed.
- [x] Leave the worktree edited but unstaged/uncommitted for user-controlled finalization.
