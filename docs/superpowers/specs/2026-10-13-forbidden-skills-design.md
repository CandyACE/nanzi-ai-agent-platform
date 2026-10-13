# 禁用公共技能（forbidden_skills）设计

日期：2026-10-13

## 需求

「禁用资源」页原本只能禁用工具（内置 / 自定义 API / MCP）与 shell 命令关键字，现在还要能
**禁用选定的公共技能**——被禁用户彻底不能使用这些技能。

## 语义决策（与用户逐轮确认）

| 决策点 | 结论 | 理由 |
| --- | --- | --- |
| 禁用强度 | **彻底不可用** | 清单不列、工具拒绝、不注入（扫描 / 点名）、不铺到会话工作区，**显式挂载也拒绝**。用户明确要求「禁用了的，显式挂载里面也不能用」 |
| 与个人技能的关系 | **不禁同名个人技能** | 禁的是"平台发布的那一份"；用户自建的同名技能属于他自己的资源，运行时本来就是个人覆盖公共 |
| 优先级 | 黑名单 > 智能体白名单 | 智能体绑定了该技能，被禁用户也不可用 |
| 作用域 | 用户级 + 角色级 | 与 `forbidden_tools` 完全平行；都通过 `resource_type="forbidden_skill"` 存 `ai_agent_resource_permissions` |

## 数据与权限：零迁移

复用 `ResourcePermission`，新增第 10 个 `resource_type="forbidden_skill"`（`resource_id` 存技能 id）。
`resource_type` 是 `String(20)` 自由字符串（`forbidden_skill` 15 字符），且当初 `forbidden_tool` /
`forbidden_command` 也没有迁移脚本——**本次无表结构变更、无迁移 SQL**。

接入点（`app/services/permission_service.py` 5 处 + schema）：

1. `PermissionSet.forbidden_skills` + 复用既有归一化 validator（去空白、大小写不敏感去重、≤100 字符）
2. `PermissionSetDetail.forbidden_skills`
3. `_aggregate_permissions` 读取合并 `elif p.resource_type == "forbidden_skill"`
4. `types_to_update` 列表（用户级与角色级各一处）
5. 用户级 / 角色级保存循环各写一行 `forbidden_skill`
6. `_build_permission_details` 回显组装

## 候选目录

`GET /api/portal/tools/forbidden-catalog` 响应新增 `skill_candidates`，元素为
`{id, label, description, group_key, group}`，`group_key` / `group` 固定 `skill:__all__` / 「公共技能」
（保留字段以便前端复用同一套分组渲染）。

候选只列**已启用的平台（全局）技能**，由新增的 `list_global_skill_metas()` 提供——刻意不调用
`list_skill_metas()`：后者会按 `user_info` 合并个人技能，配置页显示用户自己的技能既越权也误导；
而且它依赖"没有 user_info 就没有个人技能"这一隐式行为（首版实现踩到过，测试里 patch 了
`get_user_personal_skills_dir` 就直接暴露了）。

## 运行时拦截（五个点）

策略集合统一由 `app/services/ai/skills/policy.py::get_forbidden_skill_ids()` 提供：
从 `ResourcePermission` 读、角色级已在 `get_user_permissions` 合并、管理员放行、失败降级返回空集合
（与技能链路各处"出错即降级为空"的风格一致，避免权限服务抖动放大成会话不可用）。

| # | 拦截点 | 实现 |
| --- | --- | --- |
| 1 | 技能清单 / 自动注入 | `list_skill_metas(..., excluded_skill_ids=)` 在**与个人技能合并之前**过滤 global；`scan_relevant_skills` / `resolve_skills_from_query` 只是透传（它们内部都走 `list_skill_metas`，一处过滤即可） |
| 2 | 工具 `list_available_skills` / `read_skill_instruction` | 两个工具改为 `async`（需要 await 查权限），把禁用集合传进 `list_skill_metas`；读取被禁技能时 matched 为 `None`，自然落到既有的「不存在、已禁用，或不在当前智能体可用 Skills 范围内」分支，零新增文案 |
| 3 | 会话工作区物化 | `discover_platform_skill_paths(..., forbidden_skill_ids=)` 过滤 global；两个调用点（`get_local_workspace` 与沙箱降级的 host-only 构建）在调用前 `await get_forbidden_skill_ids(...)` |
| 4 | 显式挂载 / 会话固定资源 | `SkillInjector.inject_skills` 在 `active_skills` 定稿后调用 `drop_forbidden_skill_items(active_skills, await get_forbidden_skill_ids())`；放在计算 `mounted_skill_ids` **之前**，这样被禁技能也不会被当作"已挂载"而跳过后续逻辑 |
| 5 | 老会话残留 | `_preseed_session_skills` 的幂等分支改为"不重建 + 反向清理" |

### 老会话残留的坑（实测踩到）

`_preseed_session_skills` 原本"索引已存在就直接 return"，所以权限收紧前铺好的技能会一直留在
会话 `skills/` 里，agent 直接读文件即可绕过禁用。

首版清理按"技能 id 的 basename"比对目录名，**测试直接抓到它会把全部技能删掉**：会话目录名是
`sanitize(SKILL.md 的 name)`（冲突时还带 `_1` 后缀），跟技能 id 毫无关系。最终改为按**内容哈希**
反向清理——与播种逻辑的判重口径完全一致：

- `_skill_content_hashes(skill_paths)` 算当前可用技能的 `sha256(SKILL.md)`；任一读不出来即返回 `None`
- `_prune_stale_session_skills` 删除哈希不在集合中的目录，并同步 `.skills` 索引（否则
  `AgentScope.initialize` 会以为内容仍在而跳过复制，留下悬空条目）
- 集合为 `None` 或空时**不做任何清理**：那更可能是技能源目录临时不可读，误删整份快照的代价
  远大于多留一会儿

这个反向清理同时修掉了智能体白名单收窄（`skills_custom` 改动）留下的同类残留。

## 前端

复用 `ForbiddenToolCatalog.vue`，新增 `resource?: 'tools' | 'skills'` prop：`skills` 模式只渲染一个
大组「禁用选定的公共技能」，折叠 / 搜索 / `(n/m)` 计数 / 全选 / 有选中变红全部沿用同一套纯函数。
两个配置页（`Users.vue` / `Roles.vue`）各挂一个实例绑定 `permissionData.forbidden_skills`；
「禁用资源」tab 徽标口径扩展为 **禁用工具数 + 禁用命令数 + 禁用技能数**。

## 测试

- `tests/ai/test_forbidden_skills_policy.py`（11 项）：公共技能被禁后消失、同名个人技能仍可用、
  扫描与点名两条路都拿不到、工作区物化过滤、挂载过滤纯函数、策略集合（普通用户 / 管理员 / 失败降级）、
  工具清单隐藏与读取拒绝、快照反向清理与"空集合不误删"
- `tests/api/test_forbidden_skill_catalog_api_contract.py`（5 项）：候选只列已启用全局技能、
  schema 归一化、`resource_type` 长度证明无需迁移、聚合读取、保存/回显链路源码级契约

## 明确不做

不修「智能体白名单在显式挂载路径不校验」这个通用缺口——本次只让**禁用**这一层在挂载路径生效，
改动范围可控。
