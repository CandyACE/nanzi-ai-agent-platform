# 浏览器导航截图竞态修复实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复服务端浏览器导航期间截图 500、页面上下文销毁和导航超时导致的空白/旧截图问题，不调整 Python 运行环境。

**Architecture:** 截图接口按请求中的 `snapshot_id` 读取已生成的截图文件，避免为展示图片再次执行 DOM 快照；浏览器 Worker 对导航后的快照使用有限重试，并把导航超时转化为可继续获取当前页面状态的结果。现有 WebSocket 会话协议保持不变。

**Tech Stack:** FastAPI、Playwright async API、pytest、Vue 3 WebSocket viewer。

---

### Task 1: 固化截图文件读取契约

**Files:**
- Modify: `app/api/v1/endpoints/browser.py`
- Test: `tests/api/v1/test_browser_sessions.py`

- [x] **Step 1: Write the failing test**

  验证带 `snapshot_id` 的截图请求直接使用已有快照截图，不调用 `browser_runtime.snapshot()`。

- [x] **Step 2: Run the focused test and verify it fails**

  Run: `venv/bin/python -m pytest tests/api/v1/test_browser_sessions.py -q`

- [x] **Step 3: Implement the minimal endpoint change**

  从查询参数读取 `snapshot_id`，通过运行时缓存获取对应快照并校验截图文件；只有没有指定快照时才允许生成当前快照，避免导航过程中重复执行 DOM 查询。

- [x] **Step 4: Run the focused test and verify it passes**

  Run: `venv/bin/python -m pytest tests/api/v1/test_browser_sessions.py -q`

### Task 2: 为浏览器会话串行化导航与快照

**Files:**
- Modify: `app/services/ai/browser/browser_runtime.py`
- Test: `tests/services/ai/test_browser_runtime.py`

- [x] **Step 1: Write the failing test**

  验证同一 `session_id` 的 `navigate()` 和 `snapshot()` 共用会话锁，不会并发进入 Worker。

- [x] **Step 2: Run the focused test and verify it fails**

  Run: `venv/bin/python -m pytest tests/services/ai/test_browser_runtime.py -q`

- [x] **Step 3: Implement the minimal per-session lock**

  在 `BrowserRuntime` 中维护按会话创建的 `asyncio.Lock`，包住 `snapshot()`、`navigate()`、`manual_input()` 及语义操作；会话锁在 runtime shutdown 时统一清理，避免关闭时删除仍可能被等待任务使用的锁。

- [x] **Step 4: Run the focused test and verify it passes**

  Run: `venv/bin/python -m pytest tests/services/ai/test_browser_runtime.py -q`

### Task 3: 处理导航上下文销毁并重试快照

**Files:**
- Modify: `app/services/ai/browser/browser_worker.py`
- Test: `tests/services/ai/test_browser_worker.py`

- [x] **Step 1: Write the failing test**

  模拟第一次 `locator.evaluate_all()` 因导航抛出 Playwright 上下文销毁错误，第二次成功，验证 Worker 返回第二次快照。

- [x] **Step 2: Run the focused test and verify it fails**

  Run: `venv/bin/python -m pytest tests/services/ai/test_browser_worker.py -q`

- [x] **Step 3: Implement bounded retry**

  仅对明确的导航上下文销毁错误重新读取页面信息和 DOM，限制重试次数，其他 Playwright 错误继续抛出。

- [x] **Step 4: Run the focused test and verify it passes**

  Run: `venv/bin/python -m pytest tests/services/ai/test_browser_worker.py -q`

### Task 4: 让导航超时后返回当前页面状态

**Files:**
- Modify: `app/services/ai/browser/browser_worker.py`
- Test: `tests/services/ai/test_browser_worker.py`

- [x] **Step 1: Write the failing test**

  模拟 `page.goto()` 抛出 Playwright 超时，但页面 URL 已更新，验证 `navigate()` 返回当前页面信息而不是直接失败。

- [x] **Step 2: Run the focused test and verify it fails**

  Run: `venv/bin/python -m pytest tests/services/ai/test_browser_worker.py -q`

- [x] **Step 3: Implement timeout fallback**

  仅捕获导航超时，校验当前 URL 后继续返回页面信息；如果当前 URL 无效或页面不可用，仍抛出原错误。

- [x] **Step 4: Run the complete regression set**

  Run: `venv/bin/python -m pytest tests/services/ai/test_browser_worker.py tests/services/ai/test_browser_session_service.py tests/api/v1/test_browser_sessions.py tests/frontend/test_browser_panel_contract.py -q`

  Also run: `git diff --check`
