# 主模型 fallback 提示设计

## 目标

当 AgentScope 主模型调用失败并实际切换到 `ModelConfig.fallback_model` 后，在本轮 assistant 消息正文最前明确告知用户当前回答来自 fallback 模型；普通工具失败、空回答兜底和无 fallback 的错误不显示这条提示。

## 方案

`ModelCallStatsMiddleware` 已经能看到每次调用的 `current_model` 和当前 Agent 的主模型。检测到两者不是同一个模型时，在 Agent 对象上记录一次本轮 fallback 信息。AgentScope 自身没有为 fallback 切换发出 SSE 事件，因此 `event_stream` 在收到 fallback 输出的第一个事件时生成一次 `model_fallback` SSE 事件：

```json
{
  "type": "model_fallback",
  "status": "warning",
  "primary_model": "deepseek-v4-pro",
  "fallback_model": "gemma-4-31b",
  "content": "> ⚠️ 主模型 ... 调用失败，本次回答由 fallback 模型 ... 生成。"
}
```

共享的前端 SSE 分发器同时服务主聊天和 AgentDebug。它把提示插入当前消息正文最前，并增加 warning 日志；服务端正文累加器也把该事件纳入持久化内容，因此刷新历史后仍可见。提示只发一次，且不改变模型调用、工具权限、重试和 fallback 选择逻辑。

## 边界与错误处理

- 只有实际进入 fallback 模型调用时才触发；主模型正常回答不触发。
- fallback 模型名称和主模型名称仅来自已构造的运行时模型实例，不展示 API Key 或异常正文。
- 若 fallback 也失败且没有可见输出，不额外伪造成功提示。
- 缺失模型名称时使用 `unknown`，提示和日志仍可用。

## 测试

- middleware 能识别主模型与 fallback 模型并只记录 fallback 信息。
- SSE 映射只生成一次 `model_fallback`，并包含两个模型名称。
- 服务端正文累加包含 fallback 提示。
- 主聊天与 AgentDebug 共用分发器处理该事件。
