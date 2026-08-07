# Markdown Math Rendering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add shared KaTeX rendering for LaTeX formulas in AI messages and canvas Markdown.

**Architecture:** Keep `frontend/src/utils/markdown.ts` as the single Markdown rendering boundary. Configure both the normal and preview `markdown-it` instances with the same math plugin and KaTeX output, so `MessageRenderer` and `CanvasMarkdownRenderer` gain identical formula behavior without changing message payloads.

**Tech Stack:** Vue 3, TypeScript, `markdown-it`, `markdown-it-texmath`, KaTeX, highlight.js, pytest source contracts, vue-tsc.

---

### Task 1: Add the formula rendering dependencies

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`

- [x] **Step 1: Add direct runtime dependencies**

Add `katex` and `markdown-it-texmath` to `frontend/package.json` dependencies, then update the lockfile with:

```bash
npm install --save katex markdown-it-texmath
```

- [x] **Step 2: Verify package metadata**

Run:

```bash
node -e "const p=require('./package.json'); console.log(p.dependencies.katex, p.dependencies['markdown-it-texmath'])"
```

Expected: both dependency versions are printed.

### Task 2: Add failing rendering contracts

**Files:**
- Modify: `tests/frontend/test_model_thinking_config_contract.py`

- [x] **Step 1: Write formula contracts**

Add assertions that `frontend/src/utils/markdown.ts` imports KaTeX CSS and `markdown-it-texmath`, configures `texmath`, enables KaTeX rendering with `throwOnError: false`, and that `CanvasMarkdownRenderer.vue` uses `renderMarkdownPreview`.

- [x] **Step 2: Run the focused contracts**

Run:

```bash
venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_model_thinking_config_contract.py -q
```

Expected: the new formula contract fails because the renderer has no math plugin yet.

### Task 3: Implement the shared Markdown math renderer

**Files:**
- Modify: `frontend/src/utils/markdown.ts`

- [x] **Step 1: Configure the shared parser**

Import `texmath` from `markdown-it-texmath`, import `katex` CSS, and configure both MarkdownIt instances with the same math rule:

```ts
const mathOptions = {
  engine: katex,
  delimiters: ['dollars', 'brackets'],
  katexOptions: { throwOnError: false, strict: 'ignore' },
};
md.use(texmath, mathOptions);
mdPreview.use(texmath, mathOptions);
```

Keep the existing fence, link, table, and highlighting behavior unchanged.

- [x] **Step 2: Run the focused contracts**

Run the test command from Task 2. Expected: all formula contracts pass.

### Task 4: Verify message and canvas consumers

**Files:**
- Inspect: `frontend/src/components/MessageRenderer.vue`
- Inspect: `frontend/src/components/embed/CanvasMarkdownRenderer.vue`

- [x] **Step 1: Confirm shared entry points**

Verify that regular messages call `renderMarkdown` and canvas Markdown calls `renderMarkdownPreview`, with no second independent Markdown parser that would bypass the math plugin.

- [x] **Step 2: Run validation**

Run:

```bash
venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_model_thinking_config_contract.py -q
node_modules/.bin/vue-tsc --noEmit
git diff --check
```

Expected: tests pass, TypeScript exits successfully, and diff check is clean.

### Task 5: Final review

**Files:**
- Review: `frontend/src/utils/markdown.ts`
- Review: `frontend/src/components/MessageRenderer.vue`
- Review: `frontend/src/components/embed/CanvasMarkdownRenderer.vue`
- Review: `frontend/package.json`
- Review: `tests/frontend/test_model_thinking_config_contract.py`

- [x] **Step 1: Confirm scope**

Verify that only frontend dependencies, shared Markdown rendering, and focused contracts changed; no backend message format or unrelated UI behavior changed.

- [x] **Step 2: Report status**

Report the validation results and explicitly state that the working tree remains uncommitted unless the user separately requests a commit.
