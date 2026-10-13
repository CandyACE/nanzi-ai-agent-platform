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
6. `_fetch_permission_details` 回显组装

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

## 前端入口置灰（禁用后的第二处 UX 补丁）

后端拦住之后，三个"用户挂载技能"的入口仍会列出被禁技能：勾选后界面显示「已挂载」，后端却
在这次挂载上静默丢弃——用户不知道自己选了没用的东西。产品确认的处理方式是
**看得见、置灰不可选、写明原因**（从列表移除会让用户以为技能丢了）。

- `GET /api/portal/skills` 每条新增 `forbidden`，被禁技能**仍然返回**；管理员恒为 false；
  策略查询失败退化为不标记，不让技能列表 500（可用性优先）。
- 判定收敛到 `frontend/src/utils/skillForbidden.ts`：严格 `=== true` 才算被禁——缺字段按
  「未禁用」处理，旧接口与个人技能接口都不带该字段，误把可用技能锁死的代价比多显示一次提示大；
  徽标文案与「无法挂载 / 无法勾选」的原因话术也同源，不允许各入口自己写一套。
- 四处接入：会话技能中心（`SkillCascadeMenu`，含 `mountSkill` 兜底守卫，把静默失效变成明确
  toast）、会话固定资源弹窗（`ResourceScopeModal`）、任务提示词编辑器（`TaskPromptComposer`）、
  以及 `EmbedChat` 的候选归一与勾选守卫。
- 关键细节：**选中方向拦、取消方向放行**——否则「禁用之前保存过」的历史项在这一屏里再也摘不掉，
  禁用不该让人无法收拾现场。标签优先级：已挂载 > 已禁用（两者都不可点）。
- 刻意不改 `AgentManagement.vue` 与 `SkillsManagement.vue`：管理员不受禁用限制，配智能体绑定
  技能与技能管理都不应该被置灰。

## 明确不做

不修「智能体白名单在显式挂载路径不校验」这个通用缺口——本次只让**禁用**这一层在挂载路径生效，
改动范围可控。

## 代码审查修复（首版交付后的二次审查）

首版交付后做了两轮审查——功能/接口面与运行时面。下面记的是**成因**，不只是"改了什么"，
以免后续有人照现状解释、又把这些绕过路径改回来。

### 功能与接口面

| # | 问题（成因） | 修法 |
| --- | --- | --- |
| F1 | `GET /users/{id}/permissions` 返回的是「用户 ∪ 角色」**并集**，而 `PUT` 写的是**直配**。用户页"读并集→写并集"，于是角色级禁用被固化成用户级记录：角色页随后取消，该用户仍被禁；反向在用户页取消角色级禁用则无效却提示成功 | 响应新增 `direct_permissions`（仅直配）；用户页回显/提交只用它，角色来源项进只读区；`PUT` 再防御性剔除与角色级重复的项（兼容旧前端） |
| F2 | 归一化上限 100 字符，而工具名最长可到 255、MCP 名由外部控制 → 单个超长项让**整页** 422 | 上限放宽到 255，并配迁移 SQL 扩 `resource_id`（MySQL `V167` / PG `V68`） |
| F3 | 权限 tab 的显示/保存判定用**可编辑**的 `formData.role`，而拉取用**原始**的 `user.role` → 把管理员改成普通用户保存时用陈旧/空缓冲整表覆盖 | 显示、拉取、保存统一到打开时**冻结**的真实身份（`permissionSubjectRole`）+ `permissionsLoaded` 双闸门 |
| F4 | 422 的 `detail` 是数组，直接塞进 toast 渲染成 `[object Object]`；且用户页先提交资料再提交权限，权限失败时资料已落库 | 提取可读文案（`apiErrorDetail`）；改为**先权限、成功后才资料** |
| F5 | `models` 早就有 `model_fields_set` 守卫，三个 `forbidden_*` 没有 → 旧前端包不提交这些字段时会被当成"清空" | 三级字段统一按提交字段决定重建范围 |
| F6 | 权限缓存键是 `v4`，其载荷不含 `forbidden_skills` → 一旦有实时读路径就会拿到缺字段的缓存 | 升到 `v5`，并在失效时顺带清 `v4` |
| F7 | 权限 GET 失败静默 → 界面显示空配置，一保存就把真实配置写没 | 提示失败 + 未成功加载前禁止提交权限 |
| F8 | 徽标直接数数组长度，但勾一个内置能力会写入整组别名 → 数字虚高 | 改按"用户视角的条目数"统一计数（组算 1、散项各 1、命令与技能累加） |
| F9 | 命令关键字只按 ASCII 逗号切分 → 用中文逗号/顿号输入会存成永不命中的关键字（保存成功、无异常、完全不拦） | 解析函数支持 `,` `，` `、` `;` `；` 与换行；保存与计数共用同一份 |
| F10 | 候选目录接口只需登录，普通用户也能看到全部可禁用工具清单 | 收紧到 `element:user:edit` |
| F11 | 设计文档把函数名写成 `_build_permission_details`（实为 `_fetch_permission_details`）；每个配置页两个 catalog 实例各发一次相同请求 | 改名；请求做 in-flight 复用 + 短 TTL 缓存（失败不缓存） |

### 运行时面（能绕过、或方向不一致）

| # | 问题（成因） | 修法 |
| --- | --- | --- |
| A1 | **命令禁用对只读命令完全失效**。引擎的判定顺序是：Step 3「只读快速通道 → ALLOW」→ Step 4 工具 `check_permissions`；而命令黑名单只挂在 Step 4，`deny_override` 又只覆盖工具。于是禁用 `cat` 之后 `cat /etc/passwd` 照跑 | 在 `deny_override` 里补命令校验（它包裹**整个**权限解析，是唯一能覆盖快速通道的位置） |
| A2 | **被禁技能正文仍可读**：`SKILLS_DIR` 整体在公共可读根里（`list_accessible_directories` 还主动指路），且显式挂载时提示词里仍写着 `/app/data/skills/<id>/SKILL.md` 绝对路径——首版只拦住了"注入"这一层 | 读权限按当前用户可用技能收口（`fs_access.is_forbidden_platform_skill_path` 插在**白名单之前**，只认平台技能根且只比第一段完整目录名，避免 `alpha_1` 被 `alpha` 误伤；管理员豁免）；同步判定走 policy 侧 60s 进程内缓存，**拿不到集合即放行**（不能把权限抖动放大成"所有技能都读不到"），失败不写缓存；挂载提示按禁用集合清洗（含写入历史之前），前端也不再为被禁技能生成"绝对路径可读"的提示 |
| A3 | 快照清理只在**工作区创建**分支执行，缓存命中直接 `return` → 权限收紧后旧快照在进程存活期内一直可读（首版"修掉老会话残留"只做了一半） | 缓存命中分支同样按当前禁用集合清理一次 |
| A4 | **清理的权威集合选错了**：原来拿"当前请求可用的技能集合"去删共享的 `<workdir>/skills`，而 `workdir` 是会话级共享、`skills_fp` 是按智能体区分的——同一会话切到窄白名单智能体，会把**别的智能体**的技能删掉 | 改为只按**被禁技能的内容哈希**清理：只删"确定被禁"的项，绝不把"本次没允许的"当陈旧 |
| A5 | 命令黑名单只认 `{exec_command, bash}` 两个名字；沙箱终端 HTTP 接口执行命令完全不走黑名单 | 记为待办（本轮未修） |
| A6 | 无身份时三类禁用**静默 fail-open 且无日志**；技能侧查询失败 fail-open、工具/命令 fail-closed，方向不一致且不可观测 | 身份缺失与失败都留 warning/error 日志。技能侧**刻意保持 fail-open**：工具拒绝的是"这一次调用"，技能侧 fail-closed 会让整个技能清单不可用，代价不对称——用 error 级别保证可告警 |
| B1 | `current_user_info` 回退读 `u_id_val`/`id`，而生产只塞 `user_id` → 该回退是**死代码**，只能靠 ctx 兜底 | 身份抽取收敛到一个辅助函数，键顺序补 `user_id`/`uid` |
| B2 | 技能被丢弃零日志、零审计，用户侧也看不到原因 | 丢弃挂载时留 warning（列出被丢的技能 id） |
| B3 | 命令命中没有专属日志，中间件只打一行不带原因的 `behavior=deny` | 命中时按 user/tool/rule 记 warning |
| B5 | 会话快照与源技能**硬链接**，而会话 workdir 属于用户私有可写根 → 写会话副本会改到平台技能源文件，跨用户生效 | 快照改为真实复制（`copy2`）；代价是每会话一份物理副本，已被确认接受 |

**A4 的教训值得单列**：清理类逻辑的"权威集合"必须与**写入范围的共享粒度**对齐。写入按会话共享、
判定却按当前请求，就一定会在多配置场景里互相删。
