# 固化报表 CodeMirror SQL 编辑器 Implementation Plan

> **For agentic workers:** 本计划在当前会话中按任务逐项执行；每个实现步骤都先补充失败契约测试，再写最小生产代码。

**Goal:** 将共享固化报表编辑器中的 SQL `textarea` 替换为支持 SQL 高亮和标准编辑能力的 CodeMirror 6，并保持现有参数插入与试跑行为。

**Architecture:** 在 `DataPortalReportCreateModal.vue` 内创建和销毁一个 CodeMirror `EditorView`。`EditorView.updateListener` 将编辑结果同步到现有 `form.sqlContent`，表单重置时通过 dispatch 同步外部内容；快捷按钮通过当前 selection dispatch 文本变更。后端接口和参数协议保持不变。

**Tech Stack:** Vue 3 Composition API、TypeScript、CodeMirror 6、`@codemirror/lang-sql`、pytest 前端源码契约测试、vue-tsc。

---

### Task 1: 锁定 CodeMirror 集成契约

**Files:**
- Modify: `tests/frontend/test_saved_report_editor_unification_contract.py`
- Modify: `frontend/package.json`

- [ ] **Step 1: 写失败契约测试**

为共享编辑器增加以下断言：直接依赖 `@codemirror/lang-sql`，组件导入 `EditorState`/`EditorView`/`sql`，模板存在 CodeMirror 容器，代码存在编辑器创建、更新监听和销毁逻辑，快捷插入调用 CodeMirror `dispatch`。

- [ ] **Step 2: 运行测试确认失败**

运行：

```bash
pytest --confcutdir=tests/frontend tests/frontend/test_saved_report_editor_unification_contract.py -q
```

预期：新增 CodeMirror 契约断言失败，因为当前组件仍使用 `textarea` 且 `package.json` 没有直接依赖。

- [ ] **Step 3: 添加直接依赖声明**

在 `frontend/package.json` 的 `dependencies` 中增加 `@codemirror/lang-sql`，其余依赖保持不变；随后使用现有依赖安装流程更新 `frontend/package-lock.json`。

- [ ] **Step 4: 再次运行测试**

此时依赖断言应通过，组件集成断言仍失败，证明测试能区分依赖和组件实现两部分。

### Task 2: 接入 CodeMirror 编辑器生命周期

**Files:**
- Modify: `frontend/src/components/data-portal/DataPortalReportCreateModal.vue`

- [ ] **Step 1: 增加编辑器状态与创建配置**

导入 `EditorState`、`EditorView`、`basicSetup`、`sql`、`history`、`defaultKeymap`、`historyKeymap`、`keymap`、`highlightActiveLine`、`bracketMatching` 和必要的主题 API；新增 `sqlEditorHost`、`sqlEditorView`、`sqlEditorSyncing` refs。

- [ ] **Step 2: 创建和销毁编辑器**

在 SQL 容器挂载后用当前 `form.sqlContent` 创建 `EditorState`，通过 `EditorView.updateListener` 在文档变更时回写表单；新增 `destroySqlEditor`，在组件卸载和弹窗关闭时销毁实例。

- [ ] **Step 3: 处理外部 SQL 同步**

监听 `form.value.sqlContent`：仅在 CodeMirror 当前文档不一致时 dispatch 全文替换；使用同步标记避免 listener 与 watcher 相互触发。

- [ ] **Step 4: 用 CodeMirror 容器替换可见 textarea**

将原 SQL `textarea` 改为带 `ref="sqlEditorHost"` 的容器，并保留一个隐藏同步 textarea 绑定 `form.sqlContent` 作为降级载体；样式迁移到 CodeMirror 根元素及 `.cm-editor`、`.cm-scroller`、`.cm-content`、`.cm-gutters`。

### Task 3: 保持动态参数快捷插入

**Files:**
- Modify: `frontend/src/components/data-portal/DataPortalReportCreateModal.vue`

- [ ] **Step 1: 让插入逻辑读取 CodeMirror 选区**

`insertSqlFragment` 从 `sqlEditorView.value.state.selection.main` 读取 `from/to`，对插入文本执行 `dispatch`，设置光标到插入内容末尾并聚焦编辑器；编辑器尚未初始化时保留表单末尾插入降级。

- [ ] **Step 2: 保留参数校验和试跑路径**

插入前继续调用 `validateSqlParameters`，不改变 `syncCustomParameterConfigs`、`buildPreviewSql` 和试跑参数弹窗逻辑。

- [ ] **Step 3: 运行契约测试**

运行固定报表前端契约测试，预期 CodeMirror 相关断言和已有动态参数断言全部通过。

### Task 4: 类型与回归验证

**Files:**
- No additional files.

- [ ] **Step 1: 运行 TypeScript 检查**

运行：`cd frontend && npm exec -- vue-tsc --noEmit`，预期退出码为 0。

- [ ] **Step 2: 运行固定报表测试集**

运行：

```bash
pytest --confcutdir=tests/frontend \
  tests/frontend/test_saved_report_editor_unification_contract.py \
  tests/frontend/test_data_portal_report_closure_contract.py \
  tests/frontend/test_saved_reports_renaming_and_creation_contract.py \
  tests/frontend/test_chat_surface_extraction_contract.py \
  tests/frontend/test_dataset_menu_loading_contract.py -q
```

预期：全部通过。

- [ ] **Step 3: 检查补丁格式**

运行：`git diff --check`，预期无输出、退出码为 0。
