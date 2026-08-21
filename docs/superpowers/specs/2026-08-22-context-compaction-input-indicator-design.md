# 输入框上下文压缩次数与时序弹框设计

## 目标

在 EmbedChat 和 AgentDebug 的输入框上下文使用浮标展开的上下文卡片中显示当前会话的上下文压缩次数。点击卡片内的次数入口后，在输入框附近打开上下文压缩时序弹框；弹框与 ChatLogs 的“上下文”Tab 使用同一套记录模型和展示组件。

## 已确认的产品口径

- 压缩次数统计当前会话中两类事件的总数：
  - 平台事件 `context_summarized`
  - AgentScope 事件 `context_compression`
- 记录按时间顺序展示，并通过来源标签区分平台和 AgentScope。
- 继续使用现有接口 `GET /api/v1/chat/conversation/{conversation_id}/context_compactions`。
- 继续保留已有的七天 Redis 留存和最多 300 字符摘要预览，不在前端补拉完整上下文。

## 方案

### 共享数据 composable

新增 `useContextCompactions`，输入 `conversationId` 和可选请求 headers，输出：

- `contextCompactions: Ref<ContextCompactionRecord[]>`
- `contextCompactionCount: ComputedRef<number>`
- `contextCompactionsLoading: Ref<boolean>`
- `contextCompactionsError: Ref<boolean>`
- `refreshContextCompactions(force?: boolean)`

composable 使用递增请求序号，保证快速切换会话或重复刷新时旧响应不能覆盖当前会话数据。会话为空时清空记录和状态；接口失败只影响次数和弹框，不影响聊天输入和发送。

### 共享时序组件

新增 `ContextCompactionTimeline.vue`，接收记录、loading、error 和刷新回调，负责展示：

- 事件类型、来源、阶段、发生时间
- 丢弃/保留消息数
- Token 使用和预算、摘要字符数
- 可展开的摘要预览
- 加载中、失败、空记录状态

ChatLogs 的现有“上下文”Tab 改为使用该组件；输入框使用同一组件放入弹框，保持字段、标签和排序一致。

### 输入框交互

`ChatInput.vue` 增加可选 props：当前会话压缩记录、加载状态和错误状态。上下文使用浮标仍只显示用量；点击浮标展开的上下文卡片中显示“压缩 N 次”入口，不改变原使用量计算和详情卡片逻辑。

点击入口时：

1. 打开位于输入框上方的弹框；
2. 强制刷新当前会话的压缩记录；
3. 弹框内部支持关闭、刷新和摘要展开；
4. 发送中不阻断消息发送，记录请求失败显示轻量错误状态。

EmbedChat 继续传递自己的认证 headers；AgentDebug 使用默认鉴权。两个页面在会话切换、模型切换和一轮发送完成后刷新记录。

## 不采用的方案

- 不让 ChatInput 自己拼接 API 请求，避免输入组件承担会话鉴权和数据加载职责。
- 不只依赖 SSE 增量计数；SSE 可能被刷新、断线或历史会话切换打断，弹框必须以 Redis 查询结果为准。
- 不复制一份 ChatLogs 的时序模板到输入框，避免两处字段和状态逻辑漂移。

## 错误处理与边界

- 没有 `conversationId` 时不显示可点击的压缩次数入口。
- 没有记录时显示“压缩 0 次”，点击后显示空状态。
- 接口失败不清空上下文使用量，不影响发送；弹框显示“加载失败，可重试”。
- 快速切换会话时，旧请求结果必须丢弃。
- 预览内容只通过 Vue 文本插值显示，不使用 `v-html`。

## 验证

- 前端契约测试：输入框入口、次数合计、弹框、共享时序组件和 ChatLogs 复用。
- composable 行为测试：当前会话请求、headers、空会话、错误和请求竞态。
- `vue-tsc --noEmit`。
- 既有上下文使用量和 ChatLogs 测试回归。
