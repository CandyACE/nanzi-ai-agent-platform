# NanZi Apple Touch Icon Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the iPhone Home Screen icon's transparent favicon fallback with an opaque NanZi app-icon export that keeps the brand gradient and avoids the dark outer edge.

**Architecture:** Keep browser favicon and runtime branding unchanged. Add a dedicated 180×180 PNG derived from the documented main NanZi icon, fill the transparent outer area with the same brand gradient, and point only the `apple-touch-icon` declaration at that export.

**Tech Stack:** Vue/Vite static assets, HTML link metadata, Python/Pillow asset export, pytest source and image contract tests.

---

### Task 1: Lock the Apple icon contract

**Files:**
- Modify: `tests/frontend/test_nanzi_brand_assets_contract.py`

- [ ] **Step 1: Write the failing assertions**

Assert that `apple-touch-icon` points to `/apple-touch-icon.png`, that the existing SVG/PNG favicon declarations remain unchanged, that the new asset is 180×180 RGBA, and that its outer corner is opaque.

- [ ] **Step 2: Run the focused test**

Run: `venv/bin/python -m pytest tests/frontend/test_nanzi_brand_assets_contract.py -q -o addopts='' --confcutdir=tests/frontend`

Expected: FAIL because `frontend/index.html` still points Apple touch icons at `/favicon.png` and `frontend/public/apple-touch-icon.png` does not exist.

### Task 2: Generate and wire the dedicated asset

**Files:**
- Create: `docs/brand/nanzi-n-icon-apple-touch-180.png`
- Create: `frontend/public/apple-touch-icon.png`
- Modify: `frontend/index.html:7`
- Modify: `docs/brand/README.md` asset table and project integration section

- [ ] **Step 1: Export from the documented main icon**

Use `docs/brand/nanzi-n-icon.png` as the source, composite it over the NanZi three-stop blue-indigo gradient to make the full canvas opaque, then downsample to 180×180 and copy the exact export into `frontend/public/apple-touch-icon.png`.

- [ ] **Step 2: Point only Apple Home Screen metadata at the new file**

Change the `apple-touch-icon` href to `/apple-touch-icon.png`; leave `/favicon.svg`, `/favicon.png`, and runtime `DEFAULT_ICON_URL` untouched.

- [ ] **Step 3: Document the platform-specific export**

Add the new brand asset to the README as an Apple Home Screen export and state that it is opaque/full-bleed so iOS can apply its own rounded mask without exposing a dark transparent edge.

### Task 3: Verify the focused boundary

**Files:**
- Test: `tests/frontend/test_nanzi_brand_assets_contract.py`

- [ ] **Step 1: Run the focused contract test**

Run: `venv/bin/python -m pytest tests/frontend/test_nanzi_brand_assets_contract.py -q -o addopts='' --confcutdir=tests/frontend`

Expected: PASS.

- [ ] **Step 2: Check the diff and asset properties**

Run: `git diff --check` and inspect the generated PNG dimensions, alpha corners, and equality between the documented brand export and the public asset.

- [ ] **Step 3: Report scope**

Confirm that only iPhone Home Screen metadata and its dedicated asset changed; browser favicon and application branding behavior remain unchanged.
