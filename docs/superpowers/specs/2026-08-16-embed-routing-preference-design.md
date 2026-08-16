# Embed 智能体路由偏好设计

## 目标

在 Embed 的界面设置中支持用户选择“自动路由”或“默认智能体”，并将普通 Embed 用户的选择持久化到 Redis；集成方通过 `agent_id` 明确指定智能体时，强制使用集成方配置并隐藏该设置区域。

## 现状

- `ChatSettings.vue` 已承载 Embed 的界面设置。
- `EmbedChat.vue` 已有 `routingMode` 和 `expertAgentId`，但当前路由偏好主要存储在浏览器 `localStorage`。
- `/api/portal/portal-prefs` 已使用 Redis 按用户保存门户偏好。
- Embed 已支持 URL `agent_id` 锁定；同时存在 `INIT_CONFIG.agent_id` 和 Ticket 返回 `agent_id` 的集成入口。

## 方案

复用 Redis Key `agent:portal_prefs:{user_id}`，在偏好 JSON 中增加：

```json
{
  "routing_mode": "auto",
  "expert_agent_id": ""
}
```

新增专用更新接口 `PUT /api/portal/portal-prefs/routing`，避免用全量偏好更新覆盖其他设置；现有 GET 接口同时返回这两个字段。

## 配置优先级

```text
URL / INIT_CONFIG / Ticket 指定 agent_id
    > 用户 Redis 路由偏好
    > 自动路由
```

集成方指定的 agent 只作用于当前 Embed 实例，不写入用户 Redis 偏好，也不覆盖用户的默认智能体设置。

## 后端约束

- 只接受 `auto` 和 `expert` 两种模式。
- `auto` 模式清空 `expert_agent_id`。
- `expert` 模式必须提供智能体 ID，并校验智能体存在、启用、已发布且当前用户有权限。
- Redis 不可用时更新接口返回 503；读取失败时返回默认值，不阻塞页面初始化。
- 运行时继续保留现有智能体权限、数据集、表和行级权限检查。

## 前端行为

- 在 `ChatSettings.vue` 增加“智能体路由”设置区，使用两个 Tab：`自动路由`、`默认智能体`。
- 默认智能体列表只使用后端返回的当前用户可用智能体。
- 普通 Embed 初始化时读取 Redis 偏好，Redis 返回值覆盖本地默认值。
- 路由偏好不再依赖不区分用户的 routing `localStorage` 作为持久化来源，避免同一浏览器多用户串配置。
- 发生集成锁定后隐藏整个设置区，并强制保持 `expert` 模式。

## 集成锁定来源

以下任一入口提供 `agent_id` 都设置当前实例锁定状态：

- URL 查询参数 `agent_id`；
- `INIT_CONFIG.agent_id`；
- Ticket exchange 返回的 `agent_id`。

锁定状态下不能切换自动路由、不能切换其他智能体，且设置项不可见。

## 验证范围

- Redis 偏好 GET/PUT、字段校验、权限校验和保留其他偏好字段。
- 前端两个 Tab、Redis 读取、默认智能体发送 agent ID。
- URL、INIT_CONFIG、Ticket 三类锁定入口均隐藏设置并阻止切换。
- 未锁定时用户偏好正常生效；无效或已撤权的默认智能体安全回退自动路由。
