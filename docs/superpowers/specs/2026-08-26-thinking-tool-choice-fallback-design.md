# Thinking 模式下 tool_choice 参数冲突的请求级 fallback 设计

## 目标

当 OpenAI-compatible 网关在思考模式下拒绝强制工具选择，并返回明确的 HTTP 400 参数错误时，当前模型调用自动以关闭思考的方式重试一次，避免本轮请求直接失败。

fallback 只影响当前请求，不修改 `ai_models` 中的模型能力、默认状态或用户会话配置。

## 已确认的现状

- `app/services/ai/runtime/agentscope/tool_choice_compat.py` 已在调用前尝试对思考模型移除强制 `tool_choice`。
- `app/services/ai/runtime/agentscope/models.py` 将思考状态同时传给 AgentScope 原生 `parameters` 和 OpenAI-compatible API 的 `extra_body.chat_template_kwargs`。
- AgentScope 普通流式 `_call_api` 的当前项目包装层只负责注入思考参数，没有针对该类 400 的 fallback。
- 只修改 `parameters.thinking_enable` 不足以关闭 provider 侧思考，因为 `extra_body.chat_template_kwargs` 仍可能携带 `thinking=true`、`enable_thinking=true` 或 `reasoning_effort`。

## 方案

在 `PlatformOpenAIChatModel._call_api` 增加请求边界 fallback：

1. 先按当前请求原样调用父类。
2. 只捕获 OpenAI SDK 的 `BadRequestError`，并要求错误同时满足：
   - HTTP 状态为 400（若异常携带状态）；
   - 错误文本包含 `tool_choice`；
   - 错误文本明确涉及 thinking/reasoning 模式；
   - 当前模型的 `parameters.thinking_enable` 为真；
   - 当前请求确实带有非 `auto` 的强制工具选择。
3. 命中后创建当前模型的浅拷贝，复用原有 client、formatter 和凭据，但只在拷贝上：
   - 将 `parameters.thinking_enable` 设为 `False`；
   - 将 `parameters.reasoning_effort` 清空；
   - 将 `chat_template_kwargs.thinking` 和 `enable_thinking` 设为 `False`；
   - 移除 `chat_template_kwargs.reasoning_effort`；
   - 将 `tool_choice` 改为 `ToolChoice(mode="auto")`，避免再次发送 `required` 或具体函数对象；模型仍可自主选择可用工具，但不再保证必须调用某个指定工具。
4. 用该拷贝重新发起一次请求。fallback 成功后，原始模型对象和后续请求仍保持思考模式。
5. 其他 400、非思考模型、没有强制工具选择的请求，原异常原样抛出，不扩大容错范围。

## 并发与副作用边界

- 不直接修改共享模型实例的 `parameters` 或 `_chat_template_kwargs`，避免并发请求互相污染。
- 第一次请求在网关参数校验阶段失败，不应产生模型输出或工具副作用；fallback 只在异常仍处于模型请求边界时执行。fallback 使用 `auto` 后，工具调用由模型自主决定。
- fallback 只重试一次，不加入通用重试，避免把真正的业务参数错误隐藏掉。
- 记录结构化 warning，包含模型名和 fallback 原因，不记录 API Key、完整 prompt 或工具参数。

## 测试设计

新增/扩展 AgentScope runtime 聚焦测试，覆盖：

- 思考模式 + 强制 `tool_choice` 遇到匹配 400 后，第二次请求关闭思考并保留原工具选择；
- fallback 使用请求拷贝，原模型仍保持 thinking 开启；
- 非匹配 400 不 fallback；
- `tool_choice=None` 或 `tool_choice=auto` 不触发该 fallback；
- 非思考模型不触发该 fallback。

不涉及数据库迁移、模型注册配置修改、服务启动或部署操作。
