# DeepSeek V4 思考与工具调用兼容设计

## 目标

修复 DeepSeek V4 在平台会话关闭思考时仍按默认思考模式运行，进而在工具预检发送强制 `tool_choice` 时返回 HTTP 400 的问题。

## 根因

平台已经将会话级 `thinking_enable=false` 解析到 AgentScope 模型参数，但当前 OpenAI 兼容适配层发送的是 `extra_body.chat_template_kwargs.thinking/enable_thinking`。这是本地推理模板控制字段，不是官方 DeepSeek Chat Completions 的思考开关；官方端点要求 `extra_body.thinking.type=disabled` 或 `enabled`，未显式设置时默认开启思考。

因此，平台本地认为思考关闭，工具预检仍允许强制工具；DeepSeek 端却仍处于思考模式并拒绝该 `tool_choice`。

## 方案

在 `app/services/ai/runtime/agentscope/models.py` 增加 DeepSeek V4 的供应商/模型识别和请求体构造：

- `provider=deepseek` 且模型为 `deepseek-v4-pro` 或 `deepseek-v4-flash` 时，始终显式发送 `extra_body.thinking.type`。
- 会话关闭思考发送 `disabled`，开启思考发送 `enabled`；关闭时不发送 `reasoning_effort`。
- 非 DeepSeek 模型继续使用已有的 `chat_template_kwargs` 逻辑。
- 保留现有 `tool_choice_for_model`：思考开启时工具预检不强制选择，思考关闭时可保留预检强制选择。
- 保留请求级精确错误 fallback；fallback 副本必须同步使用 DeepSeek 的 `thinking.type=disabled`，不修改共享模型实例或数据库配置。

## 数据流

`EmbedChat` 的会话开关 → `/api/v1/chat/completions` 的 `debug_options.thinking_enable` → `resolve_reasoning_settings` → `AgentScopeModelConfig` → DeepSeek 专用 `extra_body.thinking`。

## 测试范围

- DeepSeek V4 开启/关闭思考时，请求体分别包含 `thinking.type=enabled/disabled`。
- DeepSeek V4 不再使用 `chat_template_kwargs` 控制思考。
- 非 DeepSeek 模型现有 `chat_template_kwargs` 行为不变。
- 关闭思考且带工具强制选择时，请求仍保留工具选择。
- 现有精确 thinking/tool_choice 400 fallback 与无关 400 不误触发。

## 不在本次范围

- 不修改 `ai_models` 表结构或模型默认配置。
- 不修改其他供应商的请求协议。
- 不运行服务、部署脚本或真实生产请求。
- 不纳入当前工作区已有的 Excel 和会话边界改动。
