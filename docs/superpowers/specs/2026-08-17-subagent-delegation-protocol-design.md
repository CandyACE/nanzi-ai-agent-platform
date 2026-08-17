# 一次性子代理委派协议增强设计

## 目标

在保留现有 `sub_agent_call(agent_name, query)` 调用兼容性的前提下，把一次性子代理委派标准化为可追踪、可取消、可限制权限和可区分终止原因的运行协议。

本次不引入独立持久化子会话、后台续聊、冷恢复或新的子代理后端。子代理仍由当前 Dispatcher/Executor 执行，但每次委派拥有明确的运行标识和父子 Trace 关系。

## 当前基础

NanZi 已有 `SubAgentRequest`、`SubAgentResult`、目标智能体权限检查、就绪校验、单层深度限制、120 秒超时、重复委派限制、权限/外部执行中断识别和结果截断。

当前子代理使用独立的 `AgentContext`，但共享父流程的 `conversation_id`、`trace_buffer`、`event_queue` 和取证账本；因此本次只补充运行级关联，不声称产生独立会话。

## 设计

### 请求

`SubAgentRequest` 增加以下可选字段：

- `run_id`：本次委派运行标识。
- `parent_trace_id`：发起委派的主流程 Trace。
- `max_depth`：本次调用允许的绝对深度上限。
- `tool_filter`：子代理允许使用的工具名称白名单，只能收窄目标智能体配置。
- `output_schema`：可选的对象型 JSON Schema，用于约束结构化结果。

模型工具参数增加对应的可选参数，但原有只传 `agent_name` 和 `query` 的调用继续有效。

### 结果

`SubAgentResult` 增加：

- `run_id`、`parent_trace_id`、`child_trace_id`；
- `stop_reason`，至少覆盖 `completed`、`empty`、`timeout`、`cancelled`、`permission_denied`、`depth_exceeded`、`invalid_output`、`failed` 和 `interrupted`；
- `structured`，保存通过 Schema 校验的 JSON 对象。

`to_tool_text()` 保持现有文本兼容行为；结构化结果和终止原因通过工具元数据、Trace 和内部调用结果保留。

### 执行

1. 生成 `run_id`，记录父 Trace。
2. 解析并校验 `max_depth`，默认仍使用当前单层委派规则；不能通过调用参数放宽平台默认上限。
3. 解析 `tool_filter`，与目标 Agent 已配置工具求交集；未知工具或试图扩大权限时 fail-closed。
4. 解析 `output_schema`，只接受 JSON 对象根节点和平台当前支持的字段类型；非法 Schema 直接返回 `invalid_output` 或参数错误，不执行子代理。
5. 创建子上下文和 Executor 时传入收窄后的工具范围、`run_id` 和父 Trace 信息。
6. 用可取消的运行信号包裹子流；超时、取消、权限中断和异常分别转换为明确 `stop_reason`。
7. 子流结束后生成带运行关联字段的结果，并继续向主模型提供兼容文本。

### 工具过滤

工具过滤只允许收窄目标智能体自己的工具配置：

```text
目标 Agent 工具集合 ∩ tool_filter
```

过滤后的集合同时用于 Prompt 工具清单和实际 Runtime Tool，不能只隐藏 Prompt 而仍允许运行时调用。

### Trace

不新增数据库表。先把关联信息写入现有 `AgentExecutionStep.meta_info`：

```json
{
  "subagent": {
    "display_name": "知识库助手",
    "agent_name": "knowledge-base",
    "run_id": "...",
    "parent_trace_id": "...",
    "child_trace_id": "...",
    "stop_reason": "completed",
    "tool_filter": ["search_knowledge_base"]
  }
}
```

现有共享 Trace buffer 继续保证主聊天的实时日志不丢失；`run_id` 和父子 Trace 字段用于检索和区分，不表示本次已经具备独立 Session 持久化。

### 页面展示

实时 SSE 会发送一条带 `subagent` 元数据的委派生命周期日志，并为子代理转发的工具日志附加相同元数据；思考卡片只展示“子代理 · 显示名称”和成功/失败状态，不展示完整 ID。

轨迹详情从 `meta_info.subagent` 展示显示名称、Run ID、父 Trace、子 Trace、停止原因和工具过滤；`/api/v1/chat/logs/{trace_id}` 与 `/api/portal/audit/traces/{trace_id}/spans` 均保留这组信息，Markdown 会话导出只保留子代理摘要。

页面展示不新增数据库表或会话恢复协议。没有子代理元数据的历史步骤继续按旧格式渲染。

## 不做的事情

- 不改主助手的路由和委派触发策略。
- 不新增独立会话表或 Session 恢复协议。
- 不让子代理获得父代理未配置的工具。
- 不把结构化输出作为所有现有子代理的强制返回格式。
- 不将取消转换为普通失败文本后继续执行。

## 验收标准

- 旧的两参数 `sub_agent_call` 调用继续运行。
- 每次委派产生唯一 `run_id`，并能从结果/Trace 关联父子执行。
- `max_depth` 只能收紧，不能绕过默认深度上限。
- `tool_filter` 同时收窄 Prompt 和 Runtime Tool，未知工具 fail-closed。
- 超时、取消、权限中断、深度拒绝和普通异常有不同 `stop_reason`。
- 合法 `output_schema` 可返回结构化对象；非法或不匹配结果不会伪装成成功。
- 现有子代理委派回归测试和原有文本结果契约保持通过。
