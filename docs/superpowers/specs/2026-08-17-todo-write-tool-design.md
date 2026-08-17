# NanZi 通用任务清单工具设计

## 目标

为 NanZi 主智能体增加一个内置 `todo_write` 工具，让模型在多步骤任务中主动维护结构化任务清单，并让前端以独立、平级于思考卡片的任务清单卡片实时展示当前任务进度。

本能力只负责通用 Agent 执行进度，不替代 ChatBI 的 `chatbi_task_plan`，不参与路由判定，不改变现有工具权限、子代理协议或业务确认流程。

## 当前基础

NanZi 已有统一的静态工具注册表、AgentScope Runtime Tool、`AgentContext.event_queue`、SSE 事件流、`process_timeline` 思考卡片快照，以及 `AgentExecutionHistory.process_timeline` 历史持久化字段。

当前工具日志和子代理日志已经通过 `event_queue` 实时汇入主执行流；`AgentService` 会把这些流事件折叠成 `process_timeline`，并在 assistant 消息落库时保存最终快照。`ChatExecutionTimeline` 被 AgentDebug 和 EmbedChat 共用，因此任务清单可以复用这条链路，不新增数据库表或独立查询接口。

## 设计

### 工具协议

新增内置工具 `todo_write`：

```json
{
  "todos": [
    { "content": "检索相关知识库", "status": "in_progress" },
    { "content": "整理并回答用户问题", "status": "pending" }
  ]
}
```

`todos` 是完整列表，每次调用整体替换当前清单。条目只包含：

- `content`：非空的人类可读任务描述；
- `status`：`pending`、`in_progress` 或 `completed`。

初版允许传空列表，用于清除当前清单；限制列表最多 20 项，单条描述最多 200 个字符，拒绝重复描述和未知字段。工具返回规范化后的列表及三类状态数量。

工具不执行业务动作、不访问外部资源、不产生 grounding evidence，也不触发用户确认。它只更新本轮运行的 UI 状态。

### 工具可见性和触发

`todo_write` 注册到现有 `ToolRegistry`，作为主 General Agent 的隐式内置工具挂载。ChatBI、Knowledge Agent、Data Agent 和子代理初版不自动挂载；主 Agent 可以通过清单记录自己委派的工作，但子代理不直接修改主清单。

提示词增加以下模型指引：

```text
当请求包含多个执行步骤、多个工具或子代理、明显的前后依赖，
或需要生成文件时，先调用 todo_write 建立任务清单。
单步问答、单次检索、单次查询不要调用 todo_write。
每完成、失败或取消一个阶段，都更新完整任务清单。
```

对于主 General Agent，平台会在工具预检阶段识别请求中的结构化多步骤信号，并把首个工具调用临时锁定为 `todo_write`；该调用返回后释放工具选择，后续仍由模型根据提示词、工具描述和真实结果决定调用子代理或其他工具。这个预检只判断是否存在多个连续动作，不判断业务意图、不选择业务工具，也不新增 LLM 意图分类调用。单步请求、ChatBI 专用流程和未挂载 `todo_write` 的 Agent 不受影响。

### 实时事件和持久化

工具成功后向当前 `AgentContext.event_queue` 推送 `todo_update` 事件：

```json
{
  "type": "todo_update",
  "todos": [
    { "content": "检索相关知识库", "status": "completed" },
    { "content": "整理并回答用户问题", "status": "in_progress" }
  ],
  "counts": { "pending": 0, "in_progress": 1, "completed": 1 }
}
```

事件进入现有 AgentScope SSE 合并流，由 `AgentService` 继续调用 `process_timeline` 折叠逻辑。最终清单作为 `process_timeline` 中的一个专用 `todo` 项保存到既有 assistant 历史记录中。历史恢复读取同一快照，因此不新增迁移、不新增 todo 表、不新增独立 API。

`todo_update` 是 UI/执行状态事件，不进入模型对话历史，也不作为事实证据参与 grounding。

### 前端展示

扩展现有 `ProcessTimelineItem` 联合类型，增加专用任务清单项。`ChatTodoCard` 从同一条 `processTimeline` 中取出最新清单，以独立、平级但位于 `ChatExecutionTimeline` 思考/工具轨迹卡片下方的卡片显示。这样执行过程持续追加内容时，任务清单跟随最新执行位置，不需要用户向上翻找：

- 标题栏支持手动展开和折叠，折叠时保留标题及完成进度；
- 标题栏支持关闭，关闭只影响当前页面的卡片显示，不删除任务状态或历史快照；
- 当清单中的任务全部变为 `completed` 时自动折叠，仍可手动展开查看；
- `completed`：勾选状态；
- `in_progress`：当前进行中状态；
- `pending`：未开始状态；
- 清单为空时不渲染任务区块。

AgentDebug 和 EmbedChat 继续复用同一个任务清单组件和历史 hydration 逻辑，实时事件与历史快照使用同一数据结构。任务清单显示整体进度，不替换已有工具日志、子代理日志和 reasoning 内容。

### 错误处理

- 参数结构或条目内容不合法时，工具返回标准工具错误，由模型自行修正；不写入错误清单；
- `event_queue` 不存在时仍完成内部校验并返回结果，避免 UI 通道缺失导致业务任务失败；
- SSE 断开不影响已经完成的工具调用；最终快照仍由主流程保存；
- 请求取消、失败或异常时保留最后一次有效清单，前端依据主消息状态显示任务未完成，不伪造 `completed`；
- 子代理的独立 trace 不写入主 Agent 的 todo，主 Agent 根据子代理结果自行更新对应任务。

## 不做的事情

- 不新增数据库表、任务管理 API 或跨会话项目管理；
- 不新增任务 ID、负责人、优先级、依赖图、重试策略或任务锁；
- 不让子代理和主 Agent 共享可变 todo 列表；
- 不替代 ChatBI 的 `chatbi_task_plan`；
- 不让后端根据业务路由或业务关键词自动生成任务；
- 不要求简单单步请求必须调用 `todo_write`；
- 不让平台预检替代模型维护任务清单；预检只负责让多步骤请求有机会先写入清单；
- 不修改现有工具配置格式、权限配置和子代理调用协议。

## 验收标准

- ToolRegistry 能解析 `todo_write`，主 General Agent 的实际工具 schema 中可见；
- 单步请求不会因为平台代码自动触发 todo；
- 主 General 的结构化多步骤请求首个工具调用优先为 `todo_write`，返回后可继续调用子代理或其他工具；
- 合法完整列表能返回规范化结果并产生 `todo_update` SSE 事件；
- 空列表可清除任务清单；
- 空描述、重复描述、未知状态、未知字段、超过数量或长度限制会失败且不产生更新事件；
- `todo_update` 能实时出现在 AgentDebug 和 EmbedChat 的执行卡片中；
- assistant 历史记录保存最终 todo 快照，刷新或重新打开历史后仍能恢复；
- todo 更新不进入模型历史、不计入 grounding evidence、不触发业务确认；
- 现有 ChatBI task plan、工具调用、子代理轨迹和 ask_user_question 行为保持不变；
- 相关后端、SSE、前端契约和历史恢复测试通过。
