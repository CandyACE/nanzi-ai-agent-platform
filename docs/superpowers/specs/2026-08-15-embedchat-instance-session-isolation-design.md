# EmbedChat 多实例会话隔离设计

## 背景

EmbedChat 当前使用固定的 `localStorage` 键 `yovole_embed_conv_id`，并在初始化时读取用户级 `/api/v1/chat/active`。`instance_id` 目前只用于宿主消息过滤，因此同一浏览器中打开多个 EmbedChat 实例时，消息事件可以隔离，但会话恢复仍然共享。

## 目标

- 让带 `instance_id` 的 EmbedChat 实例拥有独立的会话恢复空间。
- 让带 `instance_id` 的实例读取或写入按用户、按实例隔离的 active conversation。
- 保留主线 `Chat.vue` 及未传 `instance_id` 的旧嵌入调用方行为。
- 保留显式 `conversation_id` 的优先级，使工作台恢复指定会话的流程不受影响。

## 双轨行为

| 调用方式 | 本地会话键 | 服务端 active conversation | 显式 `conversation_id` |
| --- | --- | --- | --- |
| 未传 `instance_id` | `yovole_embed_conv_id` | 继续读取/更新 | 优先使用 |
| 传入 `instance_id` | `yovole_embed_conv_id:<encoded-instance>` | `conversation:{user_id}:active:{instance_id}` | 优先使用 |

`instance_id` 可以来自 URL 查询参数或 `INIT_CONFIG`。初始化必须先解析实例身份，再恢复本地会话，避免隔离实例先读到旧的 legacy 会话。`INIT_CONFIG` 传入新的实例身份且未指定会话时，清空当前 iframe 内存中的会话状态；同一实例未指定会话时继续当前会话，保持主线路由刷新行为。

兼容仅使用 URL token 的旧嵌入方式时，若 URL 没有 `instance_id`，组件会给父页面的 `INIT_CONFIG` 留出短暂握手窗口；若配置迟到，旧初始化及其历史请求会因初始化代际变化而丢弃，不能覆盖新实例会话。

## 不在本次范围内

- 不修改 `Chat.vue` 的主线消息协议。
- 不修改数据库结构；active conversation API 增加可选 `instance_id` 查询参数。
- 不调整 `postMessage` 的来源校验和 token 安全策略。
- 不迁移历史 legacy key；旧主线会话继续由 legacy 分支读取。

## 验证策略

- 增加 EmbedChat 源码契约测试，覆盖 legacy/实例命名空间、active API 分支和初始化顺序。
- 回归主线消息通知、URL agent 锁定及 WidgetDebugger 相关前端契约。
- 对变更文件执行 `git diff --check`。
