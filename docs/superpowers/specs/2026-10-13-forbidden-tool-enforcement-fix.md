# 禁用工具拦截修复：MCP 运行时名匹配 + 别名误判为「历史遗留」

- 日期：2026-10-13
- 状态：已修复
- 关联设计：目录来源 [v1](./2026-10-13-forbidden-tool-catalog-design.md)、分组渲染 [v2](./2026-10-13-forbidden-tool-grouping-design.md)
- 触发：用户确认「自定义 API 与 MCP 扩展工具禁用」是否也是全局拉黑时，顺着拦截链核对发现

## 0. 先确认的事实（用户的问题）

两块候选写的是同一个 `forbidden_tools`：同一个 `v-model`（[Users.vue:1223](../../../frontend/src/views/Users.vue#L1223) / Roles 页同理）、同一个 `ResourcePermission(resource_type="forbidden_tool")`（[permission_service.py:664](../../../app/services/permission_service.py#L664) 用户级 / [:749](../../../app/services/permission_service.py#L749) 角色级）、同一个拦截钩子（[agent_runtime.py:99-105](../../../app/services/ai/runtime/agentscope/agent_runtime.py#L99-L105) 的 `ToolPermissionMiddleware(deny_override=…)`）。差别只是**工具来源**（内置高危 vs 自定义 API + MCP 扩展），不是作用域。

「全局」的准确含义：配置所在维度的**所有**智能体与会话一律拦截——用户页 = 该用户，角色页 = 该角色下所有用户。

## 1. 缺陷 B（安全）：MCP 工具勾了禁用，运行时拦不住

### 证据

用真实的 `enforce_tool_forbidden` 跑出的判定（修复前）：

| 传给拦截器的工具名 | 判定 | 说明 |
| --- | --- | --- |
| `write_file` | DENY | 内置工具 |
| `Write` | DENY | 内置别名 |
| `jira_search` | DENY | MCP 在目录里的 id，也是存进库的名字 |
| `mcp_jira_search_9dc08da06a` | **放行** | MCP 运行时真实注册名 |
| `mcp_crm_query_80bfa6145a` | **放行** | 同上（`server:tool` 形式） |

### 根因

OpenAI 兼容的 Function Calling 只接受 `^[a-zA-Z0-9_-]+$`，所以 MCP 工具注册给模型时走
[model_tool_name.build_model_tool_name()](../../../app/services/ai/tools/model_tool_name.py#L24)：
`jira_search` → `mcp_jira_search_9dc08da06a`（[mcp_factory.py:140](../../../app/services/ai/tools/mcp_factory.py#L140)），而平台标识（`tool_name`、目录候选 id、写进 `forbidden_tools` 的值）是原名。

拦截侧 [tools.py:1680-1687](../../../app/services/ai/runtime/agentscope/tools.py#L1680-L1687) 只扩展内置别名表 `AGENTSCOPE_BUILTIN_TOOL_ALIASES`，没有做 MCP 名归一化 → 两侧永远匹配不上。

全仓 `forbidden_tools` 的唯一消费点就是这个函数（工具装配期不按它过滤，MCP 工具照常注册、模型照常看得见），因此**没有旁路兜住**：配置看起来生效，实际放行。

影响面：**MCP 工具**。自定义 API 工具不受影响（[generic_api.py:101](../../../app/services/ai/tools/generic_api.py#L101) 注册名就是 `tool_config.name`，与目录 id 一致）；内置工具不受影响（别名表覆盖）。

### 修法

`model_tool_name` 新增 `to_runtime_tool_names()`：平台名 → `(原名, 模型调用名)` 两个变体；拦截侧的扩展集合对每个被禁名字同时收两侧名字。变体由原名哈希确定性派生，因此不会与"可读名相同但实际不同的工具"混淆。

## 2. 缺陷 A（展示与交互）：别名被误判成「其他已禁用项（历史）」

### 现象

截图里大组 1 显示 `(3/9)`，历史区却躺着 `Write`、`Edit`——它们并没有下架，是 `write_file` / `edit_file` 的运行时别名。

### 根因

勾选一个内置能力会写入整组别名（`write_file` → `write_file` + `Write` + `write`），而 orphan 判定用的是**只含候选 `id`** 的集合，别名不在其中，于是被判为"目录里已经没有的历史项"。

后果：同一能力同时出现在"已勾选的组"与历史区；历史区的勾选框只移除**那一个名字**，容易让人误以为解除的是整个能力。

### 修法

新增纯函数 `findOrphanIds(selected, candidates)`：只有**既不是任何候选 `id`、也不在任何候选 `aliases`** 里的名字才算历史遗留；组件改为委托它（组件内不再自行计算）。

## 3. 测试

| 层 | 文件 | 覆盖 |
| --- | --- | --- |
| 后端 | `tests/ai/runtime/test_forbidden_tool_model_name_matching.py`（新增 4 项） | MCP 运行时名（无前缀与 `server:tool` 两种）拦得住；内置工具与别名的双向匹配不回归；不同工具、以及可读名相同但哈希不同的工具**不得误拦** |
| 前端 | `tests/frontend/test_forbidden_tool_grouping_behavior.py`（+1 项） | 别名不进历史区；真孤儿仍进；目录为空/加载失败时全部保留（否则用户无法解除） |
| 前端 | `tests/frontend/test_forbidden_tool_grouping_contract.py`（保真更新 1 条断言） | 由"内联写 `!catalogIds.value.has(id)`"改为断言"委托 `findOrphanIds`"，契约意图（orphan 区独立、不被搜索过滤、不参与折叠与全选）不变 |

两个缺陷都遵循「先写失败测试 → 看它精确失败 → 最小实现修复」。

## 4. 影响面

| 项 | 内容 |
| --- | --- |
| 表结构 | 无变更，无迁移 |
| 接口 | 无变更 |
| 数据 | 无需订正：已配置的禁用项本来就存平台名，修复后开始真正生效 |
| 部署 | 需重启后端并重建前端静态资源（用户执行 `./dev.sh`） |

## 5. 后续关联修复（同日二次审查）

本文只覆盖**工具**侧的匹配问题。同日对「禁用资源」整体做审查时，在**命令**侧又发现一个更严重的绕过：
AgentScope 引擎的判定顺序是「Step 3 只读快速通道 → ALLOW」先于「Step 4 工具 `check_permissions`」，
而平台的命令黑名单只挂在 Step 4，`deny_override` 当时又只覆盖工具，因此禁用 `cat` 之后
`cat /etc/passwd` 照跑（详见 `2026-10-13-forbidden-skills-design.md` 的「代码审查修复 · A1」）。
修法是在 `deny_override` 里补命令校验——它包裹整个权限解析，是唯一能覆盖只读快速通道的位置。
