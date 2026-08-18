# 浏览器审批默认值与状态视觉优化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让新建浏览器会话默认自动执行，并用紧凑、醒目的状态徽章和可关闭提示层表达安全确认状态。

**Architecture:** 后端只改变新建 `BrowserSession` 的默认值，复用已有会话仍使用数据库状态。前端 `BrowserPanel` 根据受控的 `approvalMode` 渲染状态徽章；`guarded` 时显示绝对定位的安全提示层，关闭只隐藏提示，切换回 `guarded` 时重新显示。

**Tech Stack:** FastAPI/Python 3.11、SQLAlchemy 模型服务、Vue 3 + TypeScript、pytest 前端契约测试。

---

### Task 1: 锁定新会话默认策略

**Files:**
- Modify: `app/services/ai/browser/browser_session_service.py:72-95`
- Test: `tests/services/ai/test_browser_session_service.py:48-70`

- [x] **Step 1: 写失败测试**

将 `test_open_reuses_user_profile_and_keeps_guarded_default` 改名为 `test_open_new_session_defaults_to_autopilot_and_reuse_preserves_mode`，首次创建断言 `first.approval_mode == "autopilot"`，并在第二次复用前显式将 `first.approval_mode = "guarded"`，断言复用后的 `second.approval_mode == "guarded"`。

- [x] **Step 2: 运行测试确认失败**

运行：`venv/bin/python -m pytest tests/services/ai/test_browser_session_service.py::test_open_new_session_defaults_to_autopilot_and_reuse_preserves_mode -q`

预期：失败在新会话默认值仍为 `guarded`。

- [x] **Step 3: 最小实现**

在 `BrowserSessionService.open_or_resume()` 的新建 `BrowserSession(...)` 分支，将 `approval_mode=BrowserApprovalMode.GUARDED.value` 改为 `approval_mode=BrowserApprovalMode.AUTOPILOT.value`；不要修改复用分支。

- [x] **Step 4: 运行测试确认通过**

运行同一条 pytest 命令，预期通过。

### Task 2: 增加面板状态徽章和可关闭安全提示层

**Files:**
- Modify: `frontend/src/components/embed/BrowserPanel.vue:35-120,220-360`
- Test: `tests/frontend/test_browser_panel_contract.py:8-22`

- [x] **Step 1: 写失败契约测试**

在现有面板契约测试中增加以下断言：源码包含 `showSafetyNotice`、`安全确认已开启`、`关闭安全提示`、`approvalMode === 'guarded'` 和 `watch(() => props.approvalMode`，同时保留 `autopilot` 断言。

- [x] **Step 2: 运行测试确认失败**

运行：`venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_browser_panel_contract.py -q`

预期：失败，因为当前组件没有安全提示状态和关闭逻辑。

- [x] **Step 3: 最小实现**

在 `BrowserPanel.vue` 中：

1. 增加 `showSafetyNotice = ref(true)`。
2. 增加 `watch(() => props.approvalMode, (mode, previous) => { if (mode === 'guarded' && previous !== 'guarded') showSafetyNotice.value = true; })`。
3. 标题栏状态徽章按模式切换：`guarded` 使用琥珀色高对比样式并显示 `⚠ 安全确认`，`autopilot` 使用绿色样式并显示 `✓ 自动执行`。
4. 在标题栏下方增加仅在 `approvalMode === 'guarded' && showSafetyNotice` 时渲染的绝对定位小提示层，包含“安全确认已开启”、高风险动作说明和带 `aria-label="关闭安全提示"` 的关闭按钮。
5. 保留原生 `<select>` 作为模式切换控件；提示层关闭只执行 `showSafetyNotice = false`，不触发 `update:approval-mode`。

- [x] **Step 4: 运行测试确认通过**

运行同一条前端契约测试命令，预期通过。

### Task 3: 校验默认值与视觉合同

**Files:**
- Test: `tests/services/ai/test_browser_policy.py`
- Test: `tests/services/ai/test_browser_events.py`
- Test: `tests/frontend/test_browser_panel_contract.py`

- [x] **Step 1: 运行浏览器相关回归测试**

运行：`venv/bin/python -m pytest tests/services/ai/test_browser_policy.py tests/services/ai/test_browser_events.py tests/services/ai/test_browser_session_service.py tests/frontend/test_browser_panel_contract.py --confcutdir=tests/frontend -q`

预期：全部通过。

- [x] **Step 2: 检查变更边界**

运行：`git diff --check -- app/services/ai/browser/browser_session_service.py frontend/src/components/embed/BrowserPanel.vue tests/services/ai/test_browser_session_service.py tests/frontend/test_browser_panel_contract.py docs/superpowers/specs/2026-08-18-browser-approval-default-visual-design.md docs/superpowers/plans/2026-08-18-browser-approval-default-visual-plan.md`

预期：无空白错误；不修改迁移、不覆盖已有会话数据、不改变浏览器工具权限判断。

### Task 4: 明确截图交互边界并隐藏内部目标

**Files:**
- Modify: `frontend/src/components/embed/BrowserPanel.vue:124-170,390-410`
- Test: `tests/frontend/test_browser_panel_contract.py:36-46`

- [x] **Step 1: 写失败契约测试并确认失败**

契约测试锁定截图提示、自动刷新说明、隐藏 `snapshot.elements` 列表和点击后聚焦画面容器。

- [x] **Step 2: 实现并验证**

增加“远程页面截图｜不是网页本体”提示，移除普通用户可见的内部元素列表，点击截图后调用 `viewportRef.focus({ preventScroll: true })`；前端契约测试和 `vue-tsc --noEmit` 已通过。
