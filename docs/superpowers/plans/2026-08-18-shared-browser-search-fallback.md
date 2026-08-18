# 共享浏览器联网搜索兜底 Implementation Plan

> **For agentic workers:** 按项目协作边界执行本计划；步骤使用 checkbox 跟踪，不自动 stage 或 commit。

**Goal:** 将右侧共享浏览器接入百度联网搜索失败后的最后一级兜底。

**Architecture:** HTTP 搜索和独立 Playwright 搜索继续负责各自的快速/渲染通道；失败时返回明确的 `browser_open` 下一步指令，由智能体调用现有共享浏览器工具，从而保留会话、面板事件和人工接管链路。

**Tech Stack:** Python 3.11、AgentScope 工具、Playwright、pytest。

---

### Task 1: 固化失败返回的共享浏览器兜底契约

**Files:**
- Modify: `tests/test_web_search_baidu_http.py`
- Modify: `tests/test_web_search_baidu.py`

- [x] **Step 1: 写失败测试**：HTTP 无结果、Playwright 无结果都必须返回 `browser_open` 和带查询参数的百度搜索 URL。
- [x] **Step 2: 运行失败测试**：

```bash
venv/bin/python -m pytest tests/test_web_search_baidu_http.py::test_web_search_baidu_http_no_results tests/test_web_search_baidu.py::test_web_search_baidu_no_results -q
```

Expected: FAIL，因为当前提示只指向 `web_search_baidu` 或没有共享浏览器指令。

### Task 2: 实现三级搜索兜底提示

**Files:**
- Modify: `app/services/ai/tools/advanced_auxiliary_tools.py`

- [x] **Step 1: 添加共享浏览器兜底提示构造函数**，复用 `_baidu_search_url()`，输出 `browser_open(url=...)` 和后续 `browser_snapshot` 操作说明。
- [x] **Step 2: 更新 HTTP/Playwright 搜索工具的失败返回和 docstring**，成功结果路径保持不变。
- [x] **Step 3: 运行百度搜索测试**：

```bash
venv/bin/python -m pytest tests/test_web_search_baidu_http.py tests/test_web_search_baidu.py -q
```

Expected: PASS。

### Task 3: 完成相关回归检查

**Files:**
- Test: `tests/services/ai/test_browser_events.py`
- Test: `tests/services/ai/test_browser_session_service.py`
- Test: `tests/frontend/test_browser_panel_contract.py`

- [x] **Step 1: 运行搜索、浏览器和前端契约测试。**
- [x] **Step 2: 运行前端类型检查和 `git diff --check`。**
- [x] **Step 3: 汇报改动；不启动服务、不提交代码。**
