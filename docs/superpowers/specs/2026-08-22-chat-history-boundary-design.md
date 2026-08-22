# 会话历史与本轮请求边界设计

## 背景

当前聊天页面会自动恢复 active conversation，并把页面中可见的 user/agent 消息全部提交到 `/api/v1/chat/completions`。服务端收到请求后又从 Redis 读取同一会话历史。这样会产生两类问题：

1. 普通新提问可能被误判为“客户端显式提交了较短历史前缀”，从而触发服务端历史截断；前端历史分页只加载最近 20 条时尤其容易发生。
2. 历史 assistant 回复和工具摘要会继续进入模型上下文；如果历史回复含有未完成任务或提问风格，模型可能把它延续到本轮。

此外，服务端当前使用请求消息列表的最后一条内容作为 `user_query`，但没有强制确认最后一条消息确实是 user 消息。

## 目标

- 有 `conversation_id` 的普通新提问以服务端 Redis 历史为准，不再由客户端消息数量触发历史截断。
- 普通新提问只提交当前 user 消息，减少客户端回放历史与服务端历史的重复合并。
- 服务端拒绝空消息或最后一条不是 user 的聊天请求，禁止旧 assistant/system 消息成为本轮问题。
- 明确告诉模型历史内容只是背景，历史 assistant 的未完成指令不属于本轮要求。
- 保留编辑/重新生成的显式截断行为，并确保截断失败时不继续发送。
- EmbedChat 与 AgentDebug 使用一致的请求边界。

## 非目标

- 不删除已有会话历史，不改变 `/new`、会话恢复或历史展示功能。
- 不改动 Docker 沙箱生命周期、工具执行权限和上下文 token 预算算法。
- 不重构整个 AgentService 或拆分现有大型 Vue 文件。

## 设计

### 请求边界

前端在带有 `conversation_id` 的普通发送流程中只构造当前 user 消息；编辑/重发流程仍先调用 `/api/v1/chat/history/truncate`，成功后再发送新的当前 user 消息。无会话 ID 的兼容请求继续允许携带客户端上下文。

服务端对带有 `conversation_id` 的请求：

1. 校验消息列表非空。
2. 校验最后一条消息 `role == "user"` 且内容非空。
3. 从 Redis 读取会话历史。
4. 追加当前 user 消息到上下文，但不根据客户端消息前缀长度截断 Redis。

客户端消息前缀长度只保留为兼容辅助信息，不再触发普通 completion 内的 `truncate_history()`。

### 历史上下文提示

在主助手、知识助手和数据助手使用的系统提示中增加统一边界说明：历史消息仅供理解上下文、指代和会话连续性；历史 assistant 回复中的任务、问题、建议和未完成指令不能自动继承；本轮必须以最新 user 消息为执行目标。

### 错误处理

- 空 `messages`：返回 HTTP 400。
- 带 `conversation_id` 但最后一条不是 user 或 user 内容为空：返回 HTTP 400。
- 编辑/重发的显式历史截断失败：保持现有前端阻断发送行为。
- 不带 `conversation_id` 的兼容调用不增加新的历史校验限制，但仍保持现有消息列表语义。

## 影响文件

- `app/api/v1/endpoints/chat.py`：增加请求边界校验。
- `app/services/ai/agent_service.py`：移除普通 completion 的隐式历史截断，并校验当前 user 消息。
- `app/services/ai/executors/prompts.py` 或对应共享系统提示入口：增加历史边界说明。
- `frontend/src/views/EmbedChat.vue`：普通会话只发送当前 user 消息。
- `frontend/src/views/AgentDebug.vue`：采用相同的当前轮请求构造逻辑。
- `tests/api/v1/`、`tests/services/ai/`、`tests/frontend/`：覆盖请求边界、历史不截断和双入口契约。

## 验证标准

- 普通新提问不会调用 `memory_service.truncate_history()`。
- 历史中包含“考题”“继续执行”等 assistant 内容时，当前主机名查询的 `user_query` 仍是主机名问题。
- 非 user 末条请求被拒绝。
- 编辑/重发仍能在显式截断后发送，并且截断失败不会发送。
- 相关 pytest、前端契约测试、`vue-tsc --noEmit`、Ruff 和 `git diff --check` 通过。
