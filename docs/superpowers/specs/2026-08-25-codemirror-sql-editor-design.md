# 固化报表 CodeMirror SQL 编辑器设计

## 目标

将固定报表创建/编辑弹窗中的 SQL 输入区域从普通 `textarea` 升级为 CodeMirror 6 编辑器，在保留现有表单、动态参数快捷插入和 SQL 试跑流程的前提下，提供真正的 SQL 编辑体验。

## 范围

- 只改前端共享组件 `DataPortalReportCreateModal.vue`，因此手动新增、AI 固化新增和 AI 编辑统一生效。
- 直接声明 CodeMirror 运行依赖，并补充 SQL 语言包。
- 提供 SQL 语法高亮、行号、当前行高亮、括号匹配、撤销/重做和基本编辑历史。
- 继续支持 `form.sqlContent` 的双向同步、光标位置插入动态参数、现有参数校验和试跑逻辑。
- 保留当前深色编辑器视觉风格，避免影响弹窗布局。
- 本次不接入数据库元数据自动补全，不修改后端 SQL 预览、权限校验或参数协议。

## 方案

使用 CodeMirror 6 的 `EditorState`、`EditorView`、SQL language extension 和基础 commands 创建一个编辑器实例。编辑器状态由组件内部持有，初始化时从 `form.sqlContent` 读取；用户编辑通过 `EditorView.updateListener` 回写 `form.sqlContent`。当表单因打开新报表、编辑既有报表或 AI 草稿而重置时，使用 `EditorView.dispatch` 更新文档，避免重新创建实例。

动态参数快捷插入继续复用现有 `insertSqlFragment` 行为，但插入目标改为 CodeMirror 当前选择区：通过 `state.selection.main` 取得选区，再用 `dispatch({ changes, selection })` 写入并恢复焦点。这样快捷按钮和手工输入共享同一个编辑器状态。

## 生命周期与错误处理

- 弹窗打开且 SQL 容器已渲染后创建编辑器；弹窗关闭或组件卸载时销毁 `EditorView`，避免监听器和 DOM 泄漏。
- `v-model` 外部同步时只在文档内容不一致时 dispatch，防止更新循环。
- 编辑器初始化失败不阻断表单保存；组件保留一个隐藏的同步 textarea 作为无障碍/降级同步载体，主交互仍显示 CodeMirror。
- CodeMirror 只负责编辑，不绕过现有 SELECT 校验、数据源选择、权限预检和试跑参数弹窗。

## 验证

- 前端契约测试检查直接依赖、CodeMirror 初始化、SQL language extension、双向同步和快捷插入 dispatch 存在。
- 运行固定报表相关前端契约测试。
- 运行 `npm exec -- vue-tsc --noEmit` 做 TypeScript 检查。
- 运行 `git diff --check` 检查补丁格式。

