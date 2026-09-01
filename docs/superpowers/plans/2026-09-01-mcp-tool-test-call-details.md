# MCP Tool Test Call Details Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 MCP 工具测试台增加“调用详情”Tab，展示本次测试实际发送的参数及返回结果。

**Architecture:** 在现有 `McpToolTester.vue` 内增加 Tab 状态和请求快照状态。输入区继续使用现有表单；执行前保存请求体快照，执行结束自动切换到详情区；详情区复用已有响应格式化和复制逻辑，并为请求 JSON 增加复制入口。

**Tech Stack:** Vue 3、TypeScript、Tailwind CSS、pytest 前端契约测试。

---

### Task 1: Add failing frontend contract coverage

**Files:**
- Modify: `tests/frontend/test_mcp_tool_tester_result_contract.py`

- [x] **Step 1: Add assertions for the details tab contract**

Assert that the component contains the tab labels, tab state, request snapshot, automatic details selection, request formatter, and request copy handler.

- [x] **Step 2: Run the focused contract test and verify it fails**

Run: `pytest --confcutdir=tests/frontend tests/frontend/test_mcp_tool_tester_result_contract.py -q`

Expected: FAIL because the new tab and request-detail symbols do not exist yet.

### Task 2: Implement request snapshot and tab behavior

**Files:**
- Modify: `frontend/src/components/system/McpToolTester.vue`

- [x] **Step 1: Add state and computed request display**

Add `activeTab`, `requestPayload`, `requestCopied`, a formatted JSON computed value, and a request copy handler. Reset these with the existing tool watcher.

- [x] **Step 2: Capture the exact request payload before posting**

Build `{ arguments: clonedArgs }` before `axios.post`, store it, and switch to the details tab in both the success/business-failure and network-error paths.

- [x] **Step 3: Split the template into input and details tabs**

Render a tablist. Keep the current parameter form under “参数输入”. Put sanitized auth, request JSON, and the existing formatted response area under “调用详情”. Show an empty prompt before the first execution.

### Task 3: Verify frontend behavior

**Files:**
- No additional files.

- [x] **Step 1: Run the focused contract test**

Run: `pytest --confcutdir=tests/frontend tests/frontend/test_mcp_tool_tester_result_contract.py -q`

Expected: PASS.

- [x] **Step 2: Run frontend type checking**

Run from `frontend`: `./node_modules/.bin/vue-tsc --noEmit`

Expected: PASS; if the environment lacks dependencies, report that as an environment blocker.

- [x] **Step 3: Run diff whitespace validation**

Run: `git diff --check -- frontend/src/components/system/McpToolTester.vue tests/frontend/test_mcp_tool_tester_result_contract.py`

Expected: no output and exit code 0.
