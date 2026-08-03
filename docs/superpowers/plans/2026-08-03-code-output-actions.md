# Code Output Actions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为可执行代码画布的运行输出增加复制与发送到 AI 分析两个悬浮操作，并修复相关元数据与文件写入边界。

**Architecture:** `ChatCanvas` 负责聚合运行输出并发出分析事件；父页面接收事件，将带有脚本、状态、stdout/stderr 的分析问题预填充到现有 `ChatInput`，由用户确认发送。工作区新建文件在后端对最终目标执行真实路径校验，画布 payload 保留语言元数据。

**Tech Stack:** Vue 3 + TypeScript、现有 ChatCanvas/ChatInput 事件、FastAPI 文件系统接口、pytest 源码契约测试。

---

### Task 1: Write failing contracts for output actions and metadata

**Files:**
- Modify: `tests/frontend/test_code_execution_canvas_contract.py`
- Modify: `tests/frontend/test_canvas_content_save_contract.py`

- [ ] Add assertions for two output action buttons, full-output copy, and an `analyze-output` event carrying execution context.
- [ ] Add assertions that `WorkspaceCanvasPayload` preserves `langName` and `runnable`, and that the parent handles output analysis by setting `userInput` before sending.
- [ ] Add a backend regression test for create-entry rejecting a final target that resolves outside the authorized workspace through a symlink.
- [ ] Run focused tests and confirm they fail for missing behavior.

### Task 2: Implement output actions and parent analysis handoff

**Files:**
- Modify: `frontend/src/components/embed/ChatCanvas.vue`
- Modify: `frontend/src/views/EmbedChat.vue`
- Modify: `frontend/src/composables/chat/useWorkspaceCanvas.ts`

- [ ] Add a computed full output string from stdout/stderr/error/status and copy it through the existing clipboard utility.
- [ ] Add compact floating buttons inside the output panel; disable analysis when no output exists.
- [ ] Emit `analyze-output` with language, source code, output, and execution status; close the canvas and prefill the existing chat input instead of sending automatically.
- [ ] Preserve `langName` and `runnable` in direct canvas payload normalization.

### Task 3: Close filesystem and filename compatibility gaps

**Files:**
- Modify: `app/api/v1/endpoints/fs.py`
- Modify: `frontend/src/utils/workspaceFilePreview.ts`
- Modify: `frontend/src/composables/chat/useWorkspaceCanvas.ts`
- Test: `tests/api/v1/test_fs_browser.py`

- [ ] Resolve the final create-entry target with `realpath`/authorized-root checks before opening it, including dangling symlink cases.
- [ ] Align `.htm` text support between frontend and backend.
- [ ] Generate default names for JavaScript, TypeScript, SQL, CSS, and JSON in addition to Python, Shell, HTML, Markdown, and text.

### Task 4: Verify

- [ ] Run focused frontend and filesystem tests.
- [ ] Run `git diff --check`.
- [ ] Report targeted results separately from any unrelated existing frontend build baseline errors.
