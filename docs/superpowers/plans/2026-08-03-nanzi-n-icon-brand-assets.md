# NanZi N Icon Brand Assets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Save a reproducible A × C NanZi N icon asset set and a Chinese design guide under `docs/brand` without changing existing frontend references.

**Architecture:** Use hand-authored SVG as the source of truth so the N geometry, gradient, nodes, and small-size simplification remain deterministic and editable. Export PNG previews from the SVG sources, then document the design rationale, tokens, sizes, and recreation prompt in Markdown.

**Tech Stack:** SVG, PNG export via an installed local rasterizer, Markdown, shell validation.

---

### Task 1: Create the reproducible vector assets and design guide

**Files:**
- Create: `docs/brand/nanzi-n-icon.svg` — 512×512 primary mark.
- Create: `docs/brand/nanzi-n-icon-favicon.svg` — simplified 32px-safe mark.
- Create: `docs/brand/README.md` — Chinese design rationale and recreation rules.

- [x] **Step 1: Add the primary and favicon-safe SVG sources**

  Use the same rounded-square background, blue-to-indigo gradient, geometric N path, and restrained connection nodes. The favicon source keeps only two nodes and omits the decorative highlight.

- [x] **Step 2: Write the design guide**

  Document the A × C concept, visual hierarchy, color values, geometry, size rules, clear space, backgrounds, prohibited variations, and a structured recreation prompt.

- [x] **Step 3: Validate SVG sources**

  Run `xmllint --noout docs/brand/nanzi-n-icon.svg docs/brand/nanzi-n-icon-favicon.svg` when available, otherwise parse both files with a local XML parser. Expected: both files parse successfully and contain no external references.

### Task 2: Export and verify PNG previews

**Files:**
- Create: `docs/brand/nanzi-n-icon.png` — 512×512 preview.
- Create: `docs/brand/nanzi-n-icon-favicon.png` — 32×32 preview.

- [x] **Step 1: Rasterize the SVG sources**

  Prefer `rsvg-convert`; otherwise use an installed ImageMagick or macOS-compatible SVG rasterizer. Keep the SVG files as the editable source of truth.

- [x] **Step 2: Verify the exported dimensions and alpha channel**

  Run `file docs/brand/nanzi-n-icon.png docs/brand/nanzi-n-icon-favicon.png` and confirm the reported dimensions are 512×512 and 32×32, with PNG/RGBA or equivalent alpha support.

- [x] **Step 3: Check the final worktree diff**

  Run `git diff --check` and `git status --short docs/brand docs/superpowers/plans/2026-08-03-nanzi-n-icon-brand-assets.md`. Expected: only the new brand assets and this plan are present; do not stage or commit them automatically.
