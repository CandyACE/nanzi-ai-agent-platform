# 浏览器自动化工具显式配置 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 19 个浏览器工具从系统隐式注入改为智能体版本显式配置，并在后台新增“浏览器自动化”工具分组。

**Architecture:** 保留浏览器工具在 `ToolRegistry._registry` 中，移除它们在 `get_system_implicit_tools()` 中的返回；显式配置继续由现有 `resolve_tool_capabilities()` 和 `get_runtime_tools()` 解析。前端沿用当前静态工具列表和分组选择契约，新增浏览器工具清单与独立分组，不增加数据库结构或历史迁移。

**Tech Stack:** Python 3.11、pytest、Vue 3、TypeScript、Vite、现有 AgentVersionEditorDrawer 工具分组组件。

---

### Task 1: 锁定后端隐式注入边界

**Files:**
- Modify: `app/services/ai/tools/registry.py:861-902`
- Test: `tests/ai/tools/test_browser_tool_configuration.py`

- [ ] **Step 1: Write the failing tests**

新增两个行为测试：`get_system_implicit_tools()` 不包含 19 个浏览器工具；`ToolRegistry.get_runtime_tools()` 接收这 19 个名称时仍返回同名 runtime specs。

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `PYTHONPATH=. venv/bin/python -m pytest tests/ai/tools/test_browser_tool_configuration.py -q`

Expected: 隐式集合测试失败，因为当前集合仍包含浏览器工具；显式解析测试保持通过或在测试环境缺依赖时单独报告。

- [ ] **Step 3: Write the minimal implementation**

从 `get_system_implicit_tools()` 返回列表移除浏览器工具；不删除 `_registry` 中的浏览器名称，保证显式配置解析链不变。

- [ ] **Step 4: Run the focused test to verify it passes**

Run: `PYTHONPATH=. venv/bin/python -m pytest tests/ai/tools/test_browser_tool_configuration.py -q`

Expected: PASS。

### Task 2: 增加“浏览器自动化”后台配置分组

**Files:**
- Modify: `frontend/src/views/AgentManagement.vue:502-643,1052-1137`
- Test: `tests/frontend/test_agent_type_form_contract.py`

- [ ] **Step 1: Write the failing contract test**

断言源码包含 `浏览器自动化` 分组、19 个浏览器工具名称，并将 `browser_open` 等工具路由到该分组而不是“其他扩展工具”。

- [ ] **Step 2: Run the focused contract test to verify it fails**

Run: `PYTHONPATH=. venv/bin/python -m pytest tests/frontend/test_agent_type_form_contract.py -q`

Expected: 新增浏览器分组断言失败。

- [ ] **Step 3: Write the minimal implementation**

在 `availableTools` 增加 19 个静态工具；扩展 `ToolGroupKey` 与 `groupedTools`，新增 `{ label: '浏览器自动化', icon: '🌐', tools: [] }`，在通用分类前优先匹配浏览器名称；保留现有分组全选、单选和版本 `tools` 持久化行为。

- [ ] **Step 4: Run the focused contract test to verify it passes**

Run: `PYTHONPATH=. venv/bin/python -m pytest tests/frontend/test_agent_type_form_contract.py -q`

Expected: PASS。

### Task 3: 运行关联回归与差异检查

**Files:**
- Test only: `tests/ai/tools/test_browser_tool_configuration.py`, `tests/services/ai/test_browser_events.py`, `tests/ai/runtime/test_tool_registry_runtime_specs.py`, `tests/frontend/test_agent_type_form_contract.py`

- [ ] **Step 1: Run backend browser and registry tests**

Run: `PYTHONPATH=. venv/bin/python -m pytest tests/ai/tools/test_browser_tool_configuration.py tests/services/ai/test_browser_events.py tests/ai/runtime/test_tool_registry_runtime_specs.py -q`

Expected: PASS；若基础设施测试依赖本地 Redis/MySQL，则只记录环境阻断，不修改无关代码。

- [ ] **Step 2: Run the frontend contract test and diff check**

Run: `PYTHONPATH=. venv/bin/python -m pytest tests/frontend/test_agent_type_form_contract.py -q` and `git diff --check`

Expected: PASS，无空白错误。

- [ ] **Step 3: Inspect final diff and status**

Run: `git diff --stat && git status --short`

Expected: 仅包含浏览器显式配置、测试和设计/计划文档；不包含数据库迁移、服务启动或历史数据写入。
