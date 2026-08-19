# 服务端自动化浏览器工具补齐 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补齐服务端自动化浏览器的交互、等待、内容读取、导航、标签页和文件传输能力，并保持权限、快照和前端刷新契约一致。

**Architecture:** 继续以 `BrowserWorker` 封装 Playwright，以 `BrowserRuntime` 负责会话锁、人工接管和快照缓存，以 `browser_tools.py` 暴露 AgentScope 工具；所有页面目标通过快照引用定位，不向模型暴露原始 Playwright 对象、任意 JS 或服务器物理路径。

**Tech Stack:** Python 3.11, FastAPI, Pydantic 2, Playwright async API, AgentScope, pytest, Vue 3/TypeScript.

---

### Task 1: 扩展浏览器数据契约和高风险策略

**Files:**
- Modify: `app/schemas/browser.py`
- Modify: `app/services/ai/browser/browser_policy.py`
- Test: `tests/services/ai/test_browser_policy.py`

- [x] **Step 1: Write failing tests** for generic browser action risk classification and bounded wait values.
- [x] **Step 2: Run the focused policy tests and verify they fail.**
- [x] **Step 3: Add wait/action/tab/download fields without exposing secrets or business-domain terms.**
- [x] **Step 4: Run the focused policy tests and verify they pass.**

### Task 2: Add Worker primitives

**Files:**
- Modify: `app/services/ai/browser/browser_worker.py`
- Test: `tests/services/ai/test_browser_worker.py`

- [x] **Step 1: Add failing tests** for press, select, visible text, hover, drag, history, tabs, upload and download.
- [x] **Step 2: Run the focused Worker tests and verify the expected missing-method failures.**
- [x] **Step 3: Implement bounded Playwright wrappers with target fingerprint validation, URL validation, and safe file roots.**
- [x] **Step 4: Run the focused Worker tests and verify they pass.**

### Task 3: Add Runtime serialization and session-safe orchestration

**Files:**
- Modify: `app/services/ai/browser/browser_runtime.py`
- Modify: `app/services/ai/browser/browser_session_service.py`
- Test: `tests/services/ai/test_browser_runtime.py`
- Test: `tests/services/ai/test_browser_session_service.py`

- [x] **Step 1: Add failing tests** for per-session locks, stale snapshot rejection, human-control waiting, tab switching and download publication.
- [x] **Step 2: Run the focused Runtime tests and verify failure.**
- [x] **Step 3: Implement Runtime methods and publish downloads through the existing capability-link service.**
- [x] **Step 4: Run the focused Runtime tests and verify pass.**

### Task 4: Expose AgentScope tools and permissions

**Files:**
- Modify: `app/services/ai/tools/browser_tools.py`
- Modify: `app/services/ai/tools/registry.py`
- Modify: `app/services/ai/runtime/agentscope/tools.py`
- Test: `tests/services/ai/test_browser_events.py`
- Test: `tests/services/ai/test_browser_tools.py`

- [x] **Step 1: Add failing tests** for tool schemas, registry visibility, read-only classification, permission handling and sensitive argument redaction.
- [x] **Step 2: Run the focused tool tests and verify failure.**
- [x] **Step 3: Add the new wrappers and permission decisions, keeping upload/download paths redacted.**
- [x] **Step 4: Run tool and event tests and verify pass.**

### Task 5: Refresh frontend after all AI browser actions

**Files:**
- Modify: `app/services/ai/runtime/agentscope/browser_events.py`
- Test: `tests/services/ai/test_browser_events.py`
- Test: `tests/frontend/test_browser_panel_contract.py`

- [x] **Step 1: Add failing event tests** for each new action.
- [x] **Step 2: Run the focused event tests and verify failure.**
- [x] **Step 3: Extend the refresh event allowlist without changing the screenshot interaction surface.**
- [x] **Step 4: Run backend and frontend contract tests and verify pass.**

### Task 6: Full focused verification and handoff

**Files:**
- No production file changes.

- [x] **Step 1: Run the browser/API target pytest suite.**
- [x] **Step 2: Run frontend contract tests and `npx vue-tsc --noEmit`.**
- [x] **Step 3: Run Python compilation and `git diff --check`.**
- [x] **Step 4: Inspect the final scoped diff and report unrun service-start/authenticated-browser acceptance separately.**
