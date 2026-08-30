# 可复用结果审查问题修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复统一可复用结果链路中的编排结果污染、知识结果跨类型复用、浏览器重复获取和 Redis 双写问题。

**Architecture:** 在 artifact 候选入口通过工具名排除纯编排结果；在 Knowledge Agent 进入复用短路前增加结果类型门禁，只允许知识类结果走免检索路径；把浏览器可见内容读取纳入事实获取工具集合；调用方只保留 `push_reusable_result` 作为 current 与 stack 的单一写入口。所有行为由单元测试锁定，不改变缺数据时回退原查询的既有策略。

**Tech Stack:** Python 3.11, pytest, FastAPI/AgentScope runtime helpers, Redis service abstraction.

---

### Task 1: 锁定 todo 与浏览器结果边界

**Files:**
- Modify: `app/services/ai/session_tool_artifact.py:31-65`
- Test: `tests/ai/test_session_tool_artifact.py`

- [ ] **Step 1: 写失败测试**

增加两个测试：`artifact_candidate_score` 对 `todo_write` 返回 0；对 `browser_read_visible` 产生的结果仍可保存，但复用过滤会移除该工具。

- [ ] **Step 2: 运行测试确认失败**

Run: `./.venv/bin/python -m pytest tests/ai/test_session_tool_artifact.py -q`
Expected: 新增的 `todo_write`/浏览器过滤断言失败。

- [ ] **Step 3: 最小实现**

将 `todo_write` 加入 `_EXCLUDED_TOOL_NAMES`，将 `browser_read_visible` 加入 `REUSABLE_RESULT_ACQUISITION_TOOLS`。

- [ ] **Step 4: 运行测试确认通过**

Run: `./.venv/bin/python -m pytest tests/ai/test_session_tool_artifact.py -q`
Expected: PASS。

---

### Task 2: 限制 Knowledge Agent 的跨类型复用

**Files:**
- Modify: `app/services/ai/runners/knowledge_agent_runner.py:497-547`
- Test: `tests/ai/runners/test_knowledge_agent_runner.py`（如已有测试文件则在其中追加；否则创建）

- [ ] **Step 1: 写失败测试**

覆盖两个行为：`result_type=knowledge` 的追问仍跳过搜索；`result_type=data` 或 `web` 时不应进入知识复用短路，必须保留 `search_knowledge_base` 并进入原知识检索路径。

- [ ] **Step 2: 运行测试确认失败**

Run: `./.venv/bin/python -m pytest tests/ai/runners/test_knowledge_agent_runner.py -q`
Expected: 跨类型复用测试失败。

- [ ] **Step 3: 最小实现**

增加一个 Knowledge Runner 专用的结果类型判断，仅当结果类型为 `knowledge`，或明确标记为知识来源的子代理结果时，才把 `reusable_decision` 视为知识 follow-up；其他类型按 `mode=none/fallback` 继续原有预检索。

- [ ] **Step 4: 运行测试确认通过**

Run: `./.venv/bin/python -m pytest tests/ai/runners/test_knowledge_agent_runner.py tests/ai/runners/test_assistant_agent_reusable_result.py -q`
Expected: PASS。

---

### Task 3: 消除 ChatBI 结果 Redis 双写

**Files:**
- Modify: `app/services/ai/runners/chatbi/followup_data.py:218-227`
- Test: `tests/ai/test_chatbi_result_stack.py`

- [ ] **Step 1: 写失败测试**

用 Redis mock 统计 ChatBI 保存结果时 current key 和 stack 的写入次数，锁定一次 current 写入和一次 stack 更新。

- [ ] **Step 2: 运行测试确认失败**

Run: `./.venv/bin/python -m pytest tests/ai/test_chatbi_result_stack.py -q`
Expected: 双写次数断言失败。

- [ ] **Step 3: 最小实现**

删除 `set_reusable_result` 调用，保留 `push_reusable_result`，让后者独占 current 与 stack 的写入。

- [ ] **Step 4: 运行测试确认通过**

Run: `./.venv/bin/python -m pytest tests/ai/test_chatbi_result_stack.py -q`
Expected: PASS。

---

### Task 4: 回归验证与差异检查

**Files:**
- Test: `tests/ai/test_reusable_result.py`
- Test: `tests/ai/test_reusable_result_routing.py`
- Test: `tests/ai/runners/test_assistant_agent_reusable_result.py`
- Test: `tests/ai/runtime/test_stream_reconcile.py`

- [ ] **Step 1: 运行可复用结果相关测试**

Run: `./.venv/bin/python -m pytest tests/ai/test_session_tool_artifact.py tests/ai/test_chatbi_result_stack.py tests/ai/test_reusable_result.py tests/ai/test_reusable_result_routing.py tests/ai/runners/test_assistant_agent_reusable_result.py tests/ai/runtime/test_stream_reconcile.py -q`

- [ ] **Step 2: 检查差异与语法**

Run: `git diff --check` and `./.venv/bin/python -m compileall -q app/services/ai`

- [ ] **Step 3: 复核改动范围**

Run: `git diff --stat` and `git status --short`;确认只包含本次修复涉及的生产代码和测试，未自动提交或启动服务。
