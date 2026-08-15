# EmbedChat 认证身份与业务上下文隔离设计

## 背景

EmbedChat 当前允许宿主通过 `INIT_CONFIG.user_info`、`SYNC_STATE` 或 `UPDATE_CONTEXT` 修改前端 `currentUser`，并把相同字段放入发送给后端的 `injected_context`。这会让页面显示身份、AI 提示词身份和 API Key 认证身份不一致。

## 目标

- 删除 `INIT_CONFIG.user_info` 协议字段及其前端身份覆盖行为。
- 宿主侧页面、工单、资产等数据统一使用 `business_context`。
- `currentUser` 只能来自服务端 API Key 校验或 `/auth/me`，宿主消息不能修改。
- 后端过滤客户端上下文中的身份字段，并保留服务端鉴权用户作为唯一可信身份。
- 保留设备类型、页面业务对象和现有普通上下文能力。

## 信任边界

| 数据 | 来源 | 用途 | 是否可由宿主修改 |
| --- | --- | --- | --- |
| `currentUser` / `user_info` | 服务端 API Key 校验 | 页面身份、服务端用户上下文、权限与记忆 | 否 |
| `business_context` | `INIT_CONFIG` / `SYNC_STATE` / `UPDATE_CONTEXT` | 当前页面业务对象与业务提示 | 是 |
| `device_type` / `display_hint` | 客户端运行时 | 输出排版提示 | 是 |

`business_context` 中的 `user_id`、`user_name`、`username`、`real_name`、`role`、`is_admin` 等身份字段会在前后端边界过滤，不能覆盖认证身份。

## 实现边界

- `Chat.vue` 不再从 localStorage 读取并发送 `INIT_CONFIG.user_info`。
- `EmbedChat.vue` 不再从宿主消息写入 `currentUser`，业务上下文改为嵌套在 `injected_context.business_context`。
- `MessageRenderer`、会话恢复等本次无关逻辑不调整。
- 后端 API 和 AgentService 双重清洗客户端 injected context，避免绕过前端直接伪造提示词身份。

## 验证策略

- 前端契约测试确认协议不再出现 `INIT_CONFIG.user_info`，且 `currentUser` 仅保留服务端写入路径。
- 后端单元测试确认业务上下文保留业务字段、过滤身份字段，并在提示词注入前使用清洗结果。
- 运行相关前端契约、后端目标测试、`vue-tsc --noEmit` 和 `git diff --check`。
