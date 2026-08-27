# 内置思考协议适配设计

## 背景

模型注册表目前只保存思考能力、默认开关和推理强度。不同 OpenAI 兼容供应商关闭思考所需的字段并不统一，统一发送 `chat_template_kwargs` 会导致部分供应商返回 400，而用户无法判断应该选择哪一种协议。

## 目标

- 用户只需要配置“思考开启/关闭”，不需要理解供应商协议。
- 在 AgentScope OpenAI-compatible 模型工厂中按 `provider` 自动生成关闭思考的请求体。
- 保留 DeepSeek V4 已有的 `thinking.type` 和工具调用兼容逻辑。
- 对未识别的自定义网关保留历史 `chat_template_kwargs` 行为。
- 不修改数据库表、模型注册表字段或前端交互。

## 内置映射

| provider | 请求体策略 | 适用条件 |
| --- | --- | --- |
| `deepseek` 的 `deepseek-v4-pro` / `deepseek-v4-flash` | `extra_body.thinking.type` | 始终按 DeepSeek V4 协议发送 |
| `kimi`、`zhipu`、`volcengine`、`volces` | `extra_body.thinking.type` | 模型被标记为支持思考时 |
| `dashscope`、`siliconflow` | `extra_body.enable_thinking` | 模型被标记为支持思考时 |
| `ollama` | `extra_body.think` | 模型被标记为支持思考时 |
| `openai`、`azure` | 使用 AgentScope/供应商原生参数 | 不额外注入供应商扩展字段 |
| `other`、未填写 provider | 历史 `chat_template_kwargs` | 兼容自定义 OpenAI 兼容网关 |

对于已知 provider 但未标记为思考能力的模型，不猜测其协议，也不注入额外字段。正常运行链路中关闭思考时会显式发送对应协议的 `false`/`disabled`，避免供应商默认开启思考。

## 边界与回退

- 只在请求工厂做协议适配；模型注册配置仍是唯一的思考能力来源。
- 已有的 DeepSeek V4 强制 `tool_choice` 兼容重试继续生效，重试请求同步使用对应供应商的关闭思考字段。
- 不把 `none` 强行转换成所有供应商都支持的 `reasoning_effort`，避免把 OpenAI 原生参数误发给不支持它的网关。
- 供应商未覆盖或模型协议不确定时，宁可不猜测，也不修改已知 provider 的请求体。

## 验证

- 使用 fake OpenAI client 检查各 provider 的最终请求参数。
- 检查已知 provider 不再收到历史 `chat_template_kwargs`。
- 检查 `other`/空 provider 的历史行为仍然保留。
- 回归 DeepSeek V4 的启用、关闭、强制工具选择和重试场景。
