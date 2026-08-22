# 上下文分项 Token 可观测性设计

## 目标

在现有上下文使用浮标和模型调用统计的基础上，区分一次 AgentScope 模型请求中：

- 系统提示词：平台规则、Agent Prompt、技能、记忆和资源等 system 消息；
- 工具：本次请求绑定给模型的工具 schema；
- 对话消息：user、assistant、tool 等非 system 消息，包括工具返回内容。

同时为输入框顶部的会话总量提供整体构成：对话消息使用当前会话 Redis 历史的完整估算，系统提示词和工具 schema 使用最近一次可用运行上下文的固定开销，并且只合并一次，不随模型调用次数重复累计。

分项采用 AgentScope `count_tokens(messages, tools)` 的统一估算口径，并明确标记为估算值；模型供应商返回的 `input_tokens` 继续作为实际请求总量。

## 范围

本期覆盖：

1. `ModelCallStatsMiddleware` 在实际模型调用记录中保存 `context_breakdown`；
2. `/model_calls` API 保留并返回该字段；
3. `ChatModelCallStatsModal` 显示三类分项；
4. 输入框的上下文详情在刷新时读取最近一次模型调用记录，显示最近一次实际请求的分项构成。
5. `/context-usage` 返回会话整体 `context_breakdown`，输入框总图条按三类分项绘制。

本期不做：发送前重新执行完整路由、权限、技能和工具解析来生成精确预览；不修改数据库；不改变现有历史上下文预算、压缩和请求保护逻辑；不把多条模型调用的 prompt/tool 开销累加成会话总量。

当 Redis 中没有可用的最近运行构成时，整体统计仍返回完整历史的 `对话消息` 分项，系统提示词和工具为 0，并标记为历史估算口径；这不会阻断上下文使用接口。

## 数据契约

```json
{
  "context_breakdown": {
    "system_prompt_tokens": 1600,
    "tools_tokens": 11000,
    "conversation_tokens": 9300,
    "total_tokens": 21900,
    "estimated": true,
    "source": "agentscope_count_tokens"
  }
}
```

分项总和通过 `total_tokens - system_prompt_tokens - tools_tokens` 归入 `conversation_tokens`，保证前端展示三项之和等于同一请求的统一估算总量。供应商实际 `input_tokens` 与估算总量可能因 tokenizer 和消息封装差异而不同。

## 数据流

```text
AgentScope on_model_call(messages, tools)
  -> context_breakdown 估算
  -> Redis model_call_stats
  -> /model_calls API
  -> ChatModelCallStatsModal

输入框刷新 context-usage
  -> context-usage 后端读取会话历史 + 最近运行固定开销
  -> 返回会话整体 context_breakdown
  -> 总图条和“会话整体构成”明细

输入框同时并行读取 model_calls
  -> 合并最近一次 context_breakdown
  -> “最近一次实际请求”对照明细
```

Redis 中不存在旧字段时保持兼容，前端隐藏分项区域，不影响旧记录查看。

## 测试与验收

- 后端测试验证 system/tools/conversation 三项及总量守恒；计数失败不能阻断模型调用；模型调用记录包含分项字段。
- API 契约验证 `ModelCallStatDetail.context_breakdown` 可返回。
- 前端契约验证输入框与模型调用弹窗展示三项、估算标识和最近一次请求字段。
- 后端测试验证整体统计不会重复累计多次模型调用的系统提示词和工具开销；前端契约验证总图条使用三段分色。
- 运行相关 pytest、Python 编译、`frontend` 目录下 `vue-tsc --noEmit`，不运行 `./dev.sh`。
