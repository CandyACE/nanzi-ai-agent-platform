# 模型思考过程展示设计

## 目标

让开启思考模式的模型在 EmbedChat、AgentDebug 及共用流式链路中，分别展示模型返回的 `reasoning_content` 和最终回答 `content`。思考内容使用独立样式，不混入普通 Markdown 回答；现有平台执行日志继续独立保留。

## 数据流

AgentScope 的 `THINKING_BLOCK_DELTA` 事件携带思考增量，后端统一转换为：

```json
{"type":"reasoning_content","content":"思考片段"}
```

最终回答仍使用：

```json
{"content":"回答片段"}
```

前端共享 SSE 分发器负责将前者追加到消息的 `reasoningContent`，将后者追加到 `content`。`thinking` 事件只负责生成状态，不承载模型思考正文。

## 前端展示

- `Message` 和 `AgentStreamMessage` 增加 `reasoningContent?: string`。
- EmbedChat、AgentDebug 在回答卡片内增加独立的“思考过程”区域，位于普通回答之前。
- 思考区域使用浅色背景、左侧强调线和可滚动文本；生成期间显示进行中状态，完成后允许折叠。
- 普通回答继续走现有 `MessageRenderer`，思考文本使用同一 Markdown 渲染能力但不进入回答内容。
- 没有思考内容时不渲染空思考区域；平台执行日志仍使用现有时间线组件。

## 兼容与边界

- 仅在 AgentScope 事件有思考增量时发送 `reasoning_content`，非思考模型保持现有 SSE 行为。
- EmbedChat、AgentDebug、ChatBI 和辅助分析复用同一事件字段；ChatBI 对思考事件现有的 SQL 计划追踪逻辑继续执行。
- 模型调用统计弹窗已有的 `reasoning_content` 展示不改动。
- 不改变会话最终回答持久化字段，不把思考文本拼入 `content`，避免历史回答和复制内容被污染。

## 测试策略

- 后端事件映射测试：`THINKING_BLOCK_DELTA` 产生独立 `reasoning_content`，正文事件仍只产生 `content`。
- 前端契约测试：共享流处理器能累积思考增量，且不改变普通回答；两个页面包含独立思考区域和字段绑定。
- 运行定向后端/前端测试，以及 `vue-tsc --noEmit`；不启动服务脚本。
