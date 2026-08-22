# Frontend TypeScript Build Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 清理当前前端严格构建中的 TypeScript 阻断错误，同时保持运行时行为和现有功能不变。

**Architecture:** 以现有运行时逻辑为基准，只在类型边界补充真实的判空、联合类型收窄、接口字段声明和 Vue 回调签名适配。对于确实表示“不可达”的分支使用窄范围断言或显式返回，不调整全局 TypeScript 严格配置、不引入大范围 `any`，每个模块修复后立即运行对应契约测试。

**Tech Stack:** Vue 3、TypeScript 5.9、vue-tsc、Vite 7、pytest 前端契约测试。

---

### Task 1: 建立错误基线并保护当前 Markdown 修复

**Files:**
- Read: `frontend/tsconfig.app.json`
- Read: `frontend/package.json`
- Test: `tests/frontend/test_internal_context_display_sanitization.py`

- [ ] **Step 1: 运行严格构建并记录错误清单**

Run: `cd frontend && ./node_modules/.bin/vue-tsc -b --pretty false`

Expected: 失败，但错误只来自当前清单；不得修改 `tsconfig.app.json` 的严格选项。

- [ ] **Step 2: 运行当前 Markdown 回归**

Run: `venv/bin/python -m pytest tests/frontend/test_internal_context_display_sanitization.py -q`

Expected: 当前 Markdown 流式换行和内部标记测试全部通过。

### Task 2: 修复纯类型/未使用符号错误

**Files:**
- Modify: `frontend/src/components/embed/ChatInput.vue`
- Modify: `frontend/src/components/metadata/RelationshipList.vue`
- Modify: `frontend/src/components/TraceLogViewer.vue`
- Modify: `frontend/src/views/AgentDebug.vue`
- Modify: `frontend/src/views/EmbedChat.vue`
- Modify: `frontend/src/views/DataSourceManagement.vue`
- Modify: `frontend/src/views/SkillsManagement.vue`
- Modify: `frontend/src/views/WidgetDebugger.vue`

- [ ] **Step 1: 删除未使用的局部引用或恢复其真实使用**

只处理 `TS6133` 指向的未使用变量；如果变量对应模板功能，则保留功能并补齐模板引用，不用删除功能代码。

- [ ] **Step 2: 运行组件契约测试**

Run: `venv/bin/python -m pytest tests/frontend/test_chat_shared_helpers_behavior.py tests/frontend/test_chat_surface_refactor_contract.py -q`

Expected: 未修改行为相关断言；若发现既有失败，记录失败文件和原因，不用放宽断言。

### Task 3: 修复数据接口和可选字段边界

**Files:**
- Modify: `frontend/src/components/chatbi/DatasetCapabilityMenu.vue`
- Modify: `frontend/src/components/chatbi/SavedReportItemCard.vue`
- Modify: `frontend/src/components/embed/BrowserPanel.vue`
- Modify: `frontend/src/components/metadata/DbTableProfileExplorerModal.vue`
- Modify: `frontend/src/composables/chat/useSavedReportWorkflow.ts`
- Modify: `frontend/src/composables/useKnowledgePortal.ts`
- Modify: `frontend/src/views/ExampleManagement.vue`
- Modify: `frontend/src/views/KnowledgeBaseManagement.vue`
- Modify: `frontend/src/views/SystemConfig.vue`

- [ ] **Step 1: 为后端已有字段补充前端类型声明**

仅当调用方已经使用字段且后端响应确实包含字段时扩展接口；不能通过 `[key: string]: any` 逃避检查。对 `custom_questions`、`user_account_name`、`page_state` 等字段，优先复用已有 API 类型定义。

- [ ] **Step 2: 为数组、响应和模板状态增加真实判空**

对 `string | undefined`、`string | null` 和数组索引结果，沿现有空状态 UI 分支处理；不得用空字符串替换会影响业务判断的缺失值。

- [ ] **Step 3: 运行对应契约测试**

Run: `venv/bin/python -m pytest tests/frontend/test_canvas_markdown_renderer_contract.py tests/frontend/test_portal_notification_bell_contract.py tests/frontend/test_dataset_menu_loading_contract.py tests/frontend/test_saved_report_delivery_markdown.py -q`

Expected: 相关组件契约通过。

### Task 4: 修复工具函数、时间线和回调类型

**Files:**
- Modify: `frontend/src/utils/agentscopeSseHandlers.ts`
- Modify: `frontend/src/utils/chartRenderer.ts`
- Modify: `frontend/src/utils/embedThoughtStages.ts`
- Modify: `frontend/src/utils/parseMcpServersPaste.ts`
- Modify: `frontend/src/utils/processTimeline.ts`
- Modify: `frontend/src/utils/quickButtons.ts`
- Modify: `frontend/src/utils/skillCreated.ts`
- Modify: `frontend/src/utils/workspaceFilePreview.ts`
- Modify: `frontend/src/composables/chat/useWorkspaceCanvas.ts`

- [ ] **Step 1: 修复索引和联合类型收窄**

在访问数组索引或联合成员前使用已有判定；对 `processTimeline` 的过滤器返回值保持 `ProcessTimelineItem` 类型，不改变时间线排序、折叠和子项数据结构。

- [ ] **Step 2: 修复回调和数据对象类型**

让回调参数与组件公开 props 的真实约定一致；对于 `CanvasPanelData`、`ChartViewMode` 等接口，只补充已实际传递的字段或在调用前提供确定的默认值。

- [ ] **Step 3: 运行工具行为测试**

Run: `venv/bin/python -m pytest tests/frontend/test_chat_shared_helpers_behavior.py tests/frontend/test_internal_context_display_sanitization.py tests/frontend/test_chatbi_result_export.py tests/frontend/test_mcp_tool_tester_result_contract.py -q`

Expected: 流式消息、时间线、Markdown 和工具相关断言通过。

### Task 5: 修复页面组件的严格类型边界

**Files:**
- Modify: `frontend/src/components/agent/AgentVersionEditorDrawer.vue`
- Modify: `frontend/src/components/system/McpServerRegistry.vue`
- Modify: `frontend/src/components/PromptAiOptimize.vue`
- Modify: `frontend/src/views/AgentManagement.vue`
- Modify: `frontend/src/views/ChatLogs.vue`
- Modify: `frontend/src/views/DataPortalHome.vue`
- Modify: `frontend/src/views/EmbedChat.vue`
- Modify: `frontend/src/views/KnowledgeBaseManagement.vue`
- Modify: `frontend/src/views/ScenarioTemplateInstall.vue`
- Modify: `frontend/src/views/SkillsManagement.vue`
- Modify: `frontend/src/views/TaskCenter.vue`

- [ ] **Step 1: 修复 props、模板和响应式数组的收窄**

在模板使用前保证对象存在；对下标访问使用现有默认项或显式空态；不改变页面展示顺序和交互事件。

- [ ] **Step 2: 修复数值/字符串和联合字面量不一致**

在数据边界统一转换，且只在原逻辑已经要求转换的地方处理；不修改后端协议和用户可见文案。

- [ ] **Step 3: 运行页面相关契约测试**

Run: `venv/bin/python -m pytest tests/frontend -q`

Expected: 所有与本次修改相关的测试通过；若有不相关既有失败，单独记录。

### Task 6: 完整验证与差异复核

**Files:**
- Verify: all modified frontend files and their tests

- [ ] **Step 1: 运行严格类型检查**

Run: `cd frontend && ./node_modules/.bin/vue-tsc -b --pretty false`

Expected: exit code 0。

- [ ] **Step 2: 运行完整生产构建**

Run: `cd frontend && npm run build`

Expected: TypeScript 检查和 Vite 构建均成功。

- [ ] **Step 3: 检查差异和工作树**

Run: `git diff --check && git status --short`

Expected: 无空白错误；只包含本次明确修复文件，不自动提交或启动服务。

