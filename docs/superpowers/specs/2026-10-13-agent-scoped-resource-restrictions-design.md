# 智能体级资源限制（用户/角色 × 智能体）设计

日期：2026-10-13
状态：**已实现**（用户「按你建议来」批准；后端 14 项 + 前端 29 项测试全绿）

## 背景与动机

平台已有**全局**的「禁用资源」：对「用户或角色」拉黑某工具 / 命令 / 技能，该用户在**所有**
智能体里都不能用。它解决的问题是"这个人绝对不许碰这些东西"。

但还有一类需求它表达不了：**同一个用户，在不同智能体里该有不同的资源边界**。典型场景是
智能体已经绑定了 10 个工具、10 个技能、10 个 MCP（含全局与个人的），管理员希望针对
「某用户或角色 × 某个智能体」再排除其中一部分，而不影响该用户在其智能体里的能力。

因此新增一层更细的作用域：**用户/角色 × 智能体 × 资源**，语义仍是"**排除**"。

## 已确认的需求边界（与用户逐条确认）

| 决策点 | 结论 |
| --- | --- |
| 限制粒度 | 按**智能体实际绑定的条目**列；MCP 作为分组标题，存的是**具体工具名**（不把 server 当独立可禁单元） |
| 限制类别 | 只含**已绑定的工具 / MCP / 技能**；「禁用命令」继续只由全局禁用资源管理 |
| 入口位置 | 权限配置 tab 的**智能体卡片**（用户/角色编辑弹框内），即现有「数据资产 → 智能体」卡片右侧 |
| 与全局的关系 | 并集：全局禁用 ∪ 智能体级禁用，任一命中即禁用 |
| 全局项在本弹框 | **只读置灰**，不允许在此单独放开（排除机制只增不减，否则与全局语义打架） |
| 与版本的关系 | 限制挂在 `agent_id` 上，**不跟版本走**；切换/发布版本不丢限制 |

## 数据模型

复用现有表 `ai_agent_resource_permissions`，新增一列作用域：

```sql
ALTER TABLE ai_agent_resource_permissions
  ADD COLUMN agent_id VARCHAR(36) NULL COMMENT '智能体级限制的作用域；NULL=全局禁用';
CREATE INDEX idx_user_agent_res ON ai_agent_resource_permissions (user_id, agent_id, resource_type);
CREATE INDEX idx_role_agent_res ON ai_agent_resource_permissions (role_id, agent_id, resource_type);
```

- `agent_id IS NULL` 表示现有全局禁用，**存量数据一行不改**。
- 非空表示只在该智能体内生效。
- `resource_type` 继续只用 `forbidden_tool`（MCP 工具也是它）与 `forbidden_skill`。
- 语义沿用"**存在即禁用**"（`resource_id` 的行存在即生效，不看 `enabled`），因此新作用域
  不引入任何新的判定形态。

迁移文件：`db-prod/V168-add_agent_scope_to_resource_permissions.sql`（MySQL）、
`db-prod-pg/V69-add_agent_scope_to_resource_permissions.sql`（PostgreSQL）。两套不通用。

**为什么不新建专表**：新表语义更干净，但要复制一整套查询 / 合并 / 缓存失效逻辑，两处判定
迟早漂移。本项目刚因"GET 读并集、PUT 写直配"的两套口径吃过一次亏（F1），不再重复。

## 判定合并

运行时有效禁用 = 全局禁用 ∪ 当前智能体的智能体级禁用。

- `PermissionService.get_user_permissions(user_id, agent_id=None)`：一次查出该用户（含角色派生）
  的禁用行，按 `agent_id` 区分：`NULL` 计入全局集合，等于 `agent_id` 计入本次作用域集合。
- `enforce_tool_forbidden(tool_name, user_id, agent_id=None)`：新增 `agent_id`，调用方从
  `get_current_agent_context().agent_id` 取（`app/core/context.py:19` 已有该字段）。
- `get_forbidden_skill_ids(user_id, agent_id=None)` 同构。
- **最需要小心的一处**：技能正文读收口 `policy.is_platform_skill_id_forbidden` 是"同步读进程内
  缓存"，其缓存 key 必须从 `user_id` 变为 `(user_id, agent_id)`，预热点（会话开始、`/api/v1/chat/fs`
  请求、原生文件工具调用）也必须带上当前智能体。否则会出现"正文读得到但注入不了"或反过来的
  不一致——这正是首版 A2 修复时踩过的同一类坑（判定发生在哪一层，就必须带那一层的上下文）。
- 权限缓存键 `sys:auth:permissions:v5:user:{id}` → `v6`，失效时顺带清 `v5`。

## 接口

端点挂在 `/api/portal/management` 前缀下（与用户/角色管理同域，便于共用 `element:user:edit` 鉴权）。

| 方法与路径 | 用途 |
| --- | --- |
| `GET /management/agents/{agent_id}/restrictable-resources?user_id=\|role_id=` | 该智能体**实际绑定**的候选清单（内置工具 / 自定义 API 工具 / MCP 按 server 分组 / 公共技能 / 个人技能；绑什么才有什么，组数量不固定），每项带 `forbidden_globally` 供前端置灰只读 |
| `GET /management/users/{user_id}/agent-restrictions/{agent_id}` | 该用户在该智能体上的限制 |
| `PUT /management/users/{user_id}/agent-restrictions/{agent_id}` | 覆盖式写入该用户的智能体级限制 |
| `GET\|PUT /management/roles/{role_id}/agent-restrictions/{agent_id}` | 角色侧同构 |
| `GET /management/agent-restrictions/counts?user_id=\|role_id=&agent_ids=a,b` | 一次取多个智能体的限制**清单**（权限页卡片角标用） |

- 权限统一为 `element:user:edit`（与 `/tools/forbidden-catalog` 一致）。
- PUT **只写 `agent_id` 等于该值的行**，绝不触碰全局行，也不删除其它智能体的行。
- 角色侧写入时，剔除已由角色派生的用户直配项，与全局禁用资源的既有做法一致。
- **`restrictable-resources` 必须带视角参数**（`user_id` 或 `role_id`）：每项的 `forbidden_globally` 是相对该主体的全局禁用而言的，不带就无法置灰，管理员会误以为能在智能体层面放开全局禁用。
- **角标接口返回清单而不是计数**：弹框在计数时会把「全局已禁用」项排除（它们置灰不可选），若后端直接给一个 COUNT，就会出现「角标 3、打开只有 1 项」。返回清单让前端复用同一个计数函数，并顺带把结果写入限制缓存，弹框随后打开即命中。
- 未迁移时（缺少 `agent_id` 列）这些接口降级：候选清单正常返回、限制清单返回空、角标全 0；作用域读写接口返回 409 并附迁移提示，而不是 500 让权限页整体打不开。

## 前端

- 权限配置 tab 的「智能体」卡片：**已勾选**（已授权）的卡片右侧加「功能限制」按钮 + 已禁数量角标；
  未勾选的卡片不显示按钮——没分配就不必配。角色编辑弹框同位置。
- 弹框：内置工具 / MCP（server 分组）/ 公共技能 / 个人技能 四个分区 + 搜索 + 分区级全选与清空 +
  底部「已选 N 项」。
- 已全局禁用的项：置灰 + 「已全局禁用」徽标 + 不可勾选。
- 允许「按 MCP server 一键禁其全部工具」作为便捷操作，落库仍是各工具名。
- 复用 `ForbiddenToolCatalog.vue` 的视觉与 `forbiddenCatalogCache` 的请求去重模式，不新造一套。

## 边界与一致性

- 管理员豁免（与三类禁用一致）。
- 被禁技能在该智能体内同样：技能入口置灰不可选 + 运行时不可用 + **正文不可读**。
- 工具改名或解绑后，限制项会变成"该智能体已不再绑定"，弹框内标注并可一键清理。
- 改动智能体级限制时，按「该用户 + 拥有该角色的用户」精确失效缓存。

## 测试计划

**后端**
1. 合并判定：全局禁 `a`、智能体 X 级禁 `b` → 在 X 里两者都不可用；在 Y 里只有 `a` 不可用。
2. 作用域隔离：智能体 X 的限制不影响 Y，也不写入全局行。
3. 角色派生 + 智能体维度：角色级限制对成员生效，且能继续派生剔除。
4. 技能正文读取：带 agent 维度后，X 里读不到、Y 里读得到（同一用户）。
5. 缓存键升版与失效范围。
6. 接口契约：仅已授权智能体可配、PUT 不碰全局行、`forbidden_globally` 正确回填。

**前端**
1. 弹框分区与计数；已全局禁用项只读且不可勾选。
2. 按钮只在已勾选卡片出现；角标数正确。
3. 保存 payload 只含该智能体的限制。

## 实施顺序

迁移与模型 → 后端判定合并 → 接口 → 前端入口与弹框 → 后端/前端测试 → `tests/CHECKLIST.md` 与本文档回填。
