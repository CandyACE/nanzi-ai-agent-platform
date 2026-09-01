# 检索测试知识库名称展示设计

## 背景

检索测试页当前在知识库选择完成后，输入框直接展示 RAGFlow Dataset ID。用户可以多选知识库，但 ID 不具备直观可读性，难以确认当前检索范围。

## 目标

- 在检索测试页展示知识库名称，而不是直接展示 Dataset ID。
- 保留多选能力和现有 RAGFlow 选择弹窗。
- 检索请求继续提交原始 Dataset ID，不改变后端接口协议。
- 选中数量较多时保持表单紧凑，不撑破左侧检索条件面板。

## 交互设计

采用名称标签方案：

- 选中 1～3 个知识库时，在知识库字段中显示名称标签。
- 每个标签显示知识库名称，并提供单独移除操作。
- 选中超过 3 个时，显示前 2 个名称标签，并显示“还有 N 个”摘要标签。
- 点击摘要区域或“选择”按钮打开现有多选选择器，可查看完整名称和重新选择。
- 知识库名称缺失或已从 RAGFlow 消失时，保留 ID 作为降级显示，避免用户无法识别当前参数。
- 标签区域设置最大高度和滚动策略，避免大量知识库导致检索表单无限增长。

## 数据流

- `KnowledgeRetrievalTest.vue` 继续以 `datasetIds: string[]` 作为请求状态。
- `RagFlowResourceSelector.vue` 在已有 `select` 事件之外提供当前选中资源的名称信息，或由父页面基于同一批 RAGFlow Dataset 数据建立 ID 到名称的映射。
- UI 只使用名称映射渲染标签；调用 `/api/portal/ragflow/retrieval-test` 时仍传 `dataset_ids: datasetIds.value`。
- 选择器加载、过滤失联 Dataset 的既有行为保持不变。

## 组件边界

- `KnowledgeRetrievalTest.vue` 负责展示摘要、维护当前选择和生成请求 payload。
- `RagFlowResourceSelector.vue` 负责加载 RAGFlow Dataset、处理多选和返回选择结果。
- 不修改 RAGFlow Retrieval API，不新增数据库字段或迁移。

## 边界与异常

- 未选择知识库时保留现有“请至少选择一个知识库”的校验。
- 名称过长时单标签省略，完整名称通过 title/详情区域可查看。
- 多个知识库名称重复时仍以 Dataset ID 区分详情，不改变实际选择。
- RAGFlow 不可用时保留现有错误提示；已保存的 ID 无法解析名称时显示 ID 降级。

## 验证

- 新增前端契约测试，验证名称标签、多选摘要、ID payload 和降级显示。
- 运行前端契约测试、`vue-tsc --noEmit` 和 `git diff --check`。
- 不启动服务、不执行真实 RAGFlow 或浏览器联调；由用户在本地页面确认视觉效果。

## 非目标

- 不改变检索接口的参数格式。
- 不把名称替换为后端检索参数。
- 不限制知识库最多可选数量。
- 不新增知识库历史记录或持久化展示偏好。
