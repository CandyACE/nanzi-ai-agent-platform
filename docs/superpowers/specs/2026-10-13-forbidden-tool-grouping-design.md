# 禁用工具目录 v2：三层分组渲染与两级折叠

- 日期：2026-10-13
- 状态：设计已评审通过，待实现
- 关联入口：用户管理 / 角色管理的「权限配置 → 禁用工具与命令」
- 前置设计：v1 见 [2026-10-13-forbidden-tool-catalog-design.md](./2026-10-13-forbidden-tool-catalog-design.md)（目录来源后端化，已实现）；本文件只改**渲染与交互**，不动目录来源与拦截语义

## 1. 现状与问题

v1 把候选目录收敛到后端接口后，[ForbiddenToolCatalog.vue](../../../frontend/src/components/system/ForbiddenToolCatalog.vue) 的渲染仍是**两个扁平区块**：

- 内置区：5～9 个候选直接铺成两栏栅格；
- 扩展区：「自定义 API 与 MCP 扩展工具禁用」把几十个 API / MCP 工具混在一起，塞进一个 `max-h-[140px]` 的内滚动区。

后果：工具一多就无法扫视——用户看不出哪些工具属于同一个 MCP 服务、哪些属于同一业务分组；两个区块本身也不能折叠，长列表永远是全长。

## 2. 目标与非目标

### 2.1 目标

1. 扩展区按**来源**分组：MCP 按 `server_name`、自定义 API 按 `SysApiTool.group_name`，工具卡片落在各自子组内。
2. 内置区按 `category` 分组（沙箱命令 / 文件操作 / 进程管理 / 知识库）。
3. 两个大组（内置、自定义 API 与 MCP）**可折叠**；子组也可折叠。
4. 组头提供 `(已选/总数)` 计数与「全选 / 取消全选」，与 `AgentVersionEditorDrawer.vue` 的分组体验对齐。
5. 折叠与全选逻辑抽成纯函数，可脱离组件做行为断言。

### 2.2 非目标

1. 不改 `aliases` 的勾选与拦截语义（勾选仍写入整组别名）。
2. 不改 orphan（历史遗留已禁用项）区的行为：不在目录里也必须可见、可解除。
3. 不改后端「内置优先、同 id 保留内置」的合并规则与候选顺序。
4. 不改 `/tools`、`/tools/mcp` 接口，不新增表结构。
5. 不做折叠状态的持久化（刷新后回到默认全展开）。

## 3. 设计

### 3.1 后端：给候选补分组字段

`GET /api/portal/tools/forbidden-catalog` 的每个 candidate 增加两个字段，**其余字段与顺序不变**：

```json
{
  "id": "jira_search",
  "label": "jira_search",
  "description": "Jira 搜索 (Jira Search): 使用 JQL 语法查询 Jira 历史工单。",
  "category": "mcp",
  "aliases": ["jira_search"],
  "group_key": "mcp:jira",
  "group": "MCP · jira"
}
```

| 来源 | `group_key` | `group`（展示标题） |
| --- | --- | --- |
| 内置 | `builtin:<category>` | 固定映射：`sandbox`→沙箱命令、`file`→文件操作、`process`→进程管理、`knowledge`→知识库；未识别的 category 回退为「其他内置工具」 |
| 自定义 API | `api:<group_name>`，空值用 `api:__ungrouped__` | `自定义 API · <group_name>`，空值 `自定义 API · 未分组` |
| MCP | `mcp:<server_name>`，空值用 `mcp:__unknown__` | `MCP · <server_name>`，空值 `MCP · 未知服务` |

设计取舍：**标签与归属由后端决定**（`group_key` 是稳定聚合键，`group` 是展示文案），前端只按 `group_key` 聚合、直接渲染 `group`。理由：MCP 服务名与 API 业务分组本来就是后端事实，内置 category 的中文映射也属于同源语义；若让前端拼标签，会再造一份与后端 category 平行的硬编码（v1 已经吃过三份硬编码漂移的亏）。

子组顺序 = 候选在响应中的首次出现顺序，前端不排序。

### 3.2 前端：三层结构

```
▼ 选择要禁用的工具（全局拉黑）              (3/14)  [全选]   [搜索框]
   ▼ 沙箱命令   (1/1)  [全选]
       ☐ 执行终端命令 (exec_command)   在沙箱中执行 Bash/shell 命令行
   ▼ 文件操作   (2/6)  [全选]
       ☐ 写入/修改文件 (write_file) …
▼ 自定义 API 与 MCP 扩展工具禁用            (0/37) [全选]
   ▼ MCP · jira                        (0/12) [全选]
       ☐ jira_search …
   ▼ 自定义 API · 履约罚款              (0/6)  [全选]
       ☐ send_email …
▼ 其他已禁用项（历史）                      ← 保持独立 amber 区，行为不变
```

- 大组头与子组头的箭头、`rotate-90` 过渡、计数写法、`[全选/取消全选]` 按钮样式**直接对齐** `AgentVersionEditorDrawer.vue` 的静态分组，不另造视觉语言。
- 大组 2 去掉 `max-h-[140px]` 内滚动：长度改由子组折叠控制，避免「滚动条里再套折叠」。极端工具量下由页面整体滚动承担。
- 内置区的红色语义、扩展区的靛蓝语义、orphan 区的 amber 语义全部保留。

### 3.3 交互细节

| 行为 | 规则 |
| --- | --- |
| 折叠状态 | `ref<Set<string>>`，大组键 `group:builtin` / `group:dynamic`，子组键直接用 `group_key`；**空集 = 全展开**（默认态），仅本组件存活期间记忆 |
| 搜索 | 命中的子组显示、未命中的隐藏；某大组下无任何命中则隐藏该大组（内置区也补上这条规则，原来它恒显示）；**搜索期间强制展开**所有分组，不写回折叠集合，清空搜索即回到原状态 |
| 计数 | `(已选/总数)`：已选 = 组内 `aliases` 命中 `selectedIds` 的候选数；总数 = 组内候选数 |
| 子组全选 | 勾选 = 组内所有候选的 `aliases` 并集并入；取消 = 移除组内所有 `aliases`（不触碰 orphan 项） |
| 大组全选 | 等于其下全部子组的并集操作 |
| orphan | 不参与分组、不参与大组全选、不被搜索过滤（必须始终可见可解除） |
| 加载/错误 | 保持现状：加载中文案、失败提示，且失败时 orphan 区仍然渲染 |

### 3.4 可测性：抽纯函数

新增 `frontend/src/utils/forbiddenToolGroups.ts`：

```ts
export interface ForbiddenToolCandidate { id, label, description, category, aliases, group_key, group }
export interface ForbiddenToolSubGroup { key: string; label: string; candidates: ForbiddenToolCandidate[] }

// 按 group_key 聚合且保序；返回 undefined 时不产生空组
export function groupCandidates(candidates: ForbiddenToolCandidate[]): ForbiddenToolSubGroup[]

// 组内已选数量（按 aliases 命中，与组件原有 isGroupSelected 同语义）
export function groupSelectedCount(group: ForbiddenToolSubGroup, selectedIds: Set<string>): number

// 组级全选/取消：返回新的选中数组，保序、去重、不改入参
export function applyGroupSelection(
  selected: string[], candidates: ForbiddenToolCandidate[], checked: boolean,
): string[]

// 搜索过滤：对 group_key / group / id / label / description 做大小写不敏感匹配
export function filterSubGroups(groups: ForbiddenToolSubGroup[], query: string): ForbiddenToolSubGroup[]
```

组件只保留渲染、折叠状态与事件绑定，聚合/计数/全选/过滤全部委托给纯函数——这样能在 node harness 里直接断言，不必挂载组件。

## 4. 测试策略

**后端**（`tests/api/test_forbidden_tool_catalog_grouping.py`，`no_infrastructure`）：

1. 三个来源的 `group_key` / `group` 取值符合 §3.1 映射表；
2. 自定义 API 的 `group_name` 为空 → `api:__ungrouped__` / 「自定义 API · 未分组」；
3. MCP 的 `server_name` 缺失 → `mcp:__unknown__` / 「MCP · 未知服务」；
4. 未识别的内置 category → 「其他内置工具」，不抛错；
5. 新增字段**不改变**既有字段（`id` / `label` / `description` / `category` / `aliases`）与内置优先合并顺序（防回归断言）。

**前端**（`tests/frontend/test_forbidden_tool_grouping_behavior.py`，node harness 直跑纯函数）：

6. `groupCandidates` 按首次出现顺序聚合、同组候选落在一组、不产生空组；
7. `groupSelectedCount` 按 `aliases` 计数（勾 `write_file` 只算 1 个候选，即使别名写了 3 个）；
8. `applyGroupSelection` 勾选/取消的并集与差集语义、结果保序去重、不改入参；
9. `filterSubGroups` 命中 `group`/`group_key`/`id`/`description` 任一即保留，空查询原样返回。

**前端契约**（`tests/frontend/test_forbidden_tool_grouping_contract.py`）：

10. 组件含三级结构、两级折叠键（`group:builtin` / `group:dynamic` / 子组 `group_key`）、计数与全选按钮、搜索强制展开；
11. 不再有 `max-h-[140px]` 内滚动；
12. orphan 区仍独立渲染且不受搜索过滤；
13. 组件改为引用 `forbiddenToolGroups.ts`，聚合逻辑不在组件内重复实现。

**验证命令**：

```
.venv/bin/python -m pytest -q tests/api/test_forbidden_tool_catalog_grouping.py
.venv/bin/python -m pytest --confcutdir=tests/frontend -q tests/frontend
.venv/bin/python -m pytest -q tests/services tests/api tests/ai
cd frontend && node --max-old-space-size=6144 ./node_modules/vue-tsc/bin/vue-tsc.js --noEmit -p tsconfig.app.json
```

## 5. 影响面

| 项 | 内容 |
| --- | --- |
| 表结构 | 无变更，无迁移 |
| 接口 | `/forbidden-catalog` 响应新增 2 个字段（向后兼容：旧前端忽略即可） |
| 前端 | 新增 1 个纯函数模块；`ForbiddenToolCatalog.vue` 由扁平两区块重写为三层结构 |
| 权限语义 | 无变化，仍按 `forbidden_tools` 名字集合拦截 |
| 部署 | 需重启后端并重建前端静态资源（用户在控制台执行 `./dev.sh`） |

## 6. 风险与取舍

1. **契约新增字段**：`group` 是展示文案放在后端，改文案要发后端。取舍是避免前端再造一份类别映射（见 §3.1）。
2. **组头全选对负向操作偏激进**：一次点击会禁用整组工具。与智能体编辑器保持一致是本次明确的产品选择；折叠 + 计数让影响面在点击前可见。
3. **折叠不持久化**：刷新回到全展开。避免引入一份需要维护的本地状态；若日后确有必要（组数继续增长），再加 `localStorage` 即可，纯函数接口不受影响。

## 7. 未决问题

无。§3 所有行为均已明确到可实现、可测试的粒度。「大组 2 是否保留内滚动」按 §3.2 结论执行：去掉内滚动，由子组折叠接管长度控制。
