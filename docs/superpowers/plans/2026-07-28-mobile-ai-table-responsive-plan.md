# Mobile AI Table Responsive Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Markdown tables in AI messages fit common mobile screens while preserving the current desktop table layout.

**Architecture:** Add a small HTML post-processing helper that classifies Markdown tables by header column count and annotates card-mode cells with `data-label`. Keep the existing table DOM and desktop CSS intact; add a narrow-screen CSS branch in `EmbedChat.vue` for compact tables and row cards. Chart table mode remains out of scope.

**Tech Stack:** Vue 3 SFC, TypeScript, Markdown-It HTML output, scoped CSS, pytest source-contract tests.

---

### Task 1: Add failing contracts for responsive table classification

**Files:**
- Modify: `tests/frontend/test_message_renderer_contract.py`
- Test: `tests/frontend/test_message_renderer_contract.py`

- [x] **Step 1: Add source-contract assertions for classification and labels**

Add tests that require the renderer to expose the following concrete contract:

```python
def test_markdown_tables_get_mobile_layout_metadata():
    source = _source("frontend/src/components/MessageRenderer.vue")

    assert "enhanceMarkdownTablesForMobile" in source
    assert "markdown-table-mobile-compact" in source
    assert "markdown-table-mobile-cards" in source
    assert "data-label" in source
    assert "MOBILE_CARD_COLUMN_THRESHOLD" in source


def test_embed_mobile_tables_use_compact_and_card_layouts():
    source = _source("frontend/src/views/EmbedChat.vue")

    assert "@media (max-width: 639px)" in source
    assert "table-layout: fixed" in source
    assert "min-width: 0" in source
    assert "td::before" in source
    assert "content: attr(data-label)" in source
    assert "grid-template-columns" in source
```

- [x] **Step 2: Run the new tests and verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/frontend/test_message_renderer_contract.py -q
```

Expected: FAIL because the helper, metadata classes, and mobile card CSS do not exist yet.

### Task 2: Implement Markdown table classification and cell labels

**Files:**
- Create: `frontend/src/utils/markdownTableResponsive.ts`
- Modify: `frontend/src/components/MessageRenderer.vue:3-8,200-204`

- [x] **Step 1: Add the pure HTML transformation helper**

Create `enhanceMarkdownTablesForMobile(tableHtml: string): string` with these exact rules:

```ts
export const MOBILE_CARD_COLUMN_THRESHOLD = 4;

export const enhanceMarkdownTablesForMobile = (tableHtml: string): string => {
  if (!/<thead\b/i.test(tableHtml) || /\b(?:colspan|rowspan)\s*=/i.test(tableHtml)) {
    return addTableClass(tableHtml, "markdown-table-mobile-compact");
  }

  const headers = [...tableHtml.matchAll(/<th\b[^>]*>([\s\S]*?)<\/th>/gi)]
    .map((match) => stripHtmlTags(match[1] || "").trim());
  if (headers.length < MOBILE_CARD_COLUMN_THRESHOLD) {
    return addTableClass(tableHtml, "markdown-table-mobile-compact");
  }

  const labeledTable = tableHtml.replace(
    /(<tbody\b[^>]*>[\s\S]*?<\/tbody>)/i,
    (tbody) => tbody.replace(/<tr\b[^>]*>[\s\S]*?<\/tr>/gi, (row) =>
      row.replace(/<td\b([^>]*)>([\s\S]*?)<\/td>/gi, (cell, attrs, inner, index) => {
        if (/\bdata-label\s*=/i.test(attrs)) return cell;
        const label = headers[index] || `第 ${index + 1} 列`;
        return `<td${attrs} data-label="${escapeAttribute(label)}">${inner}</td>`;
      }),
    ),
  );

  return addTableClass(labeledTable, "markdown-table-mobile-cards");
};
```

The helper must preserve the original table when it cannot safely classify it, escape `&`, `<`, `>`, and `"` in `data-label`, and keep all original cell HTML.

- [x] **Step 2: Apply the helper only to wrapped Markdown tables**

In `MessageRenderer.vue`, import the helper and change the existing wrapper transformation to:

```ts
res = res.replace(
  /<table\b[^>]*>[\s\S]*?<\/table>/gi,
  (table) => `<div class="markdown-table-scroll">${enhanceMarkdownTablesForMobile(table)}</div>`,
);
```

Do not call it for chart-rendered table mode or any other renderer.

### Task 3: Add the mobile A+B CSS branch

**Files:**
- Modify: `frontend/src/views/EmbedChat.vue:7211-7293`

- [x] **Step 1: Keep desktop rules unchanged**

Retain the existing wrapper border, table `min-width: 680px`, header/cell spacing, zebra rows, and hover rules outside a media query.

- [x] **Step 2: Add compact-table rules under 640px**

Add a media query that targets `.markdown-table-mobile-compact` and sets `min-width: 0`, `width: 100%`, `table-layout: fixed`, smaller padding, `font-size: 12px`, and `white-space: normal` so short tables fit without horizontal scrolling.

- [x] **Step 3: Add card-table rules under 640px**

Within the same media query, target `.markdown-table-mobile-cards` and:

```css
min-width: 0;
display: block;

/* hide only the visual header; table semantics remain in the DOM */
thead { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
tbody, tr { display: block; }
tr { margin: 0 0 10px; padding: 8px 10px; border: 1px solid #e2e8f0; border-radius: 10px; background: #fff; }
td { display: grid; grid-template-columns: minmax(72px, 34%) minmax(0, 1fr); gap: 8px; padding: 6px 0; border: 0; white-space: normal; }
td::before { content: attr(data-label); color: #64748b; font-size: 11px; font-weight: 700; }
```

Add dark-mode overrides for card background, border, label, and value colors. Override the existing first-column monospace rule for card mode so every field uses normal readable text.

### Task 4: Run focused validation and clean up

**Files:**
- Modify if needed: `tests/frontend/test_message_renderer_contract.py`, `frontend/src/utils/markdownTableResponsive.ts`, `frontend/src/components/MessageRenderer.vue`, `frontend/src/views/EmbedChat.vue`

- [x] **Step 1: Run focused frontend contracts**

```bash
.venv/bin/python -m pytest tests/frontend/test_message_renderer_contract.py -q
```

Expected: all message-renderer contract tests pass.

- [x] **Step 2: Run syntax/type checks available in the checkout**

```bash
git diff --check
cd frontend && npx vue-tsc --noEmit
```

Expected: no whitespace errors; report any pre-existing type baseline failures separately from this change.

- [x] **Step 3: Inspect the final diff**

```bash
git diff --stat
git diff -- frontend/src/utils/markdownTableResponsive.ts frontend/src/components/MessageRenderer.vue frontend/src/views/EmbedChat.vue tests/frontend/test_message_renderer_contract.py
```

Confirm that only Markdown AI-message tables gain the mobile branch, desktop `min-width: 680px` remains, chart table mode is unchanged, and no project service script was run.

### Task 5: Add a per-table mobile card/table toggle

**Files:**
- Modify: `frontend/src/components/MessageRenderer.vue:201-235`
- Modify: `frontend/src/views/EmbedChat.vue:7294-7445`
- Modify: `tests/frontend/test_message_renderer_contract.py`

- [x] **Step 1: Add the failing toggle contracts**

Require the renderer to emit a mobile-only toolbar for card-mode tables, delegate clicks through `.markdown-table-view-toggle`, and expose `aria-label` values for switching to table/card view. Require the embed CSS to restore `overflow-x: auto` and `min-width: 680px` under `.markdown-table-view-table`.

- [x] **Step 2: Implement non-persistent per-table toggling**

The renderer starts each 4+ column table with `markdown-table-view-cards`. The delegated click handler toggles `markdown-table-view-table` on the nearest wrapper, updates the button label/title/ARIA state, and does not write to localStorage or shared config.

- [x] **Step 3: Verify the toggle and existing behavior**

Run `tests/frontend/test_message_renderer_contract.py`, `npx vue-tsc --noEmit`, `git diff --check`, and the frontend build from `frontend`. Keep the existing chart table mode unchanged.
