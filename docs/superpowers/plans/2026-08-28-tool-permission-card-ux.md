# 工具调用确认卡 UX 优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让工具调用确认卡在 `EmbedChat` 与 `AgentDebug` 中清晰表达执行内容、风险范围、一次性授权语义和执行结果。

**Architecture:** 新增共享的 `ToolPermissionCard.vue`，负责确认卡的视觉层、响应式布局、可访问性和状态反馈；新增 `toolPermissionDisplay.ts`，只做保守的展示摘要与风险提示，不参与后端权限决策。两个聊天页面通过事件回传复用现有确认流和 SSE 状态。

**Tech Stack:** Vue 3、TypeScript、Tailwind CSS 3、pytest 前端契约测试、vue-tsc。

---

### Task 1: 添加展示逻辑契约

**Files:**
- Create: `frontend/src/utils/toolPermissionDisplay.ts`
- Test: `tests/frontend/test_chat_shared_helpers_behavior.py`

- [x] **Step 1: 写失败测试**

  覆盖 Bash 只读命令的友好标题、低风险摘要、命令计数、未知工具的保守风险，以及 JSON 参数回退展示。

- [x] **Step 2: 运行测试确认失败**

  Run: `pytest --confcutdir=tests/frontend tests/frontend/test_chat_shared_helpers_behavior.py -k tool_permission_display -q`

  Expected: FAIL，因为展示工具函数尚不存在。

- [x] **Step 3: 实现最小展示工具**

  解析 `tool_call.name` 和 `tool_call.args.command`，仅对白名单只读命令给出“低风险/读取服务器状态”展示；所有其他情况默认“需确认”，不改变实际权限判断。

- [x] **Step 4: 运行测试确认通过**

  Run: `pytest --confcutdir=tests/frontend tests/frontend/test_chat_shared_helpers_behavior.py -k tool_permission_display -q`

  Expected: PASS。

### Task 2: 抽取并优化共享确认卡

**Files:**
- Create: `frontend/src/components/chat/ToolPermissionCard.vue`
- Test: `tests/frontend/test_execution_stage_card_contract.py`

- [x] **Step 1: 写失败契约**

  断言共享组件包含明确的执行标题、影响范围、风险标签、命令详情折叠、一次性授权文案、提交中反馈、状态播报、响应式操作区和键盘可访问属性。

- [x] **Step 2: 运行测试确认失败**

  Run: `pytest --confcutdir=tests/frontend tests/frontend/test_execution_stage_card_contract.py -k permission_card -q`

  Expected: FAIL，因为共享组件尚不存在。

- [x] **Step 3: 实现共享组件**

  保留现有 `pendingPermission` 状态和 `submit(confirmed)` 事件；标题优先使用展示摘要，技术工具名作为标签；命令区限制高度并可折叠；审批按钮在提交中禁用并显示“正在提交…”；完成后保留结果状态。

- [x] **Step 4: 运行测试确认通过**

  Run: `pytest --confcutdir=tests/frontend tests/frontend/test_execution_stage_card_contract.py -k permission_card -q`

  Expected: PASS。

### Task 3: 接入两个聊天页面

**Files:**
- Modify: `frontend/src/views/EmbedChat.vue`
- Modify: `frontend/src/views/AgentDebug.vue`
- Test: `tests/frontend/test_execution_stage_card_contract.py`

- [x] **Step 1: 替换重复模板**

  两个页面都引入 `ToolPermissionCard`，以现有 `msg.pendingPermission` 作为 payload，并将确认事件继续交给现有 `confirmPendingPermission`。

- [x] **Step 2: 保持生命周期语义**

  等待审批时显示“等待你的确认”，点击后显示“正在继续执行…”；不把审批等待误标记成可中止的普通生成状态。

- [x] **Step 3: 增加页面接入契约**

  断言两个页面都不再保留独立的确认卡模板，并都接入共享组件。

- [x] **Step 4: 运行前端静态检查**

  Run: `vue-tsc --noEmit`

  Expected: PASS。

### Task 4: 回归验证

**Files:**
- Test: `tests/frontend/test_chat_shared_helpers_behavior.py`
- Test: `tests/frontend/test_execution_stage_card_contract.py`

- [x] **Step 1: 运行聚焦契约测试**

  Run: `pytest --confcutdir=tests/frontend tests/frontend/test_chat_shared_helpers_behavior.py tests/frontend/test_execution_stage_card_contract.py -q`

  Expected: PASS；若失败，只修复本次确认卡范围内的问题。

- [x] **Step 2: 检查差异格式**

  Run: `git diff --check -- frontend/src/components/chat/ToolPermissionCard.vue frontend/src/utils/toolPermissionDisplay.ts frontend/src/views/EmbedChat.vue frontend/src/views/AgentDebug.vue tests/frontend/test_chat_shared_helpers_behavior.py tests/frontend/test_execution_stage_card_contract.py docs/superpowers/plans/2026-08-28-tool-permission-card-ux.md`

  Expected: 无输出且退出码为 0。

- [x] **Step 3: 汇报边界**

  明确报告静态测试和类型检查结果；不声称已通过浏览器、服务、后端权限策略或真实 Bash 环境验收，因为本任务不会启动服务。
