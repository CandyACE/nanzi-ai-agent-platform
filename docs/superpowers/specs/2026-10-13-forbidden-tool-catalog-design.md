# 禁用工具目录：由后端接口驱动内置工具与扩展工具的统一渲染

- 日期：2026-10-13
- 状态：已实现（渲染分组已由 v2 重构，见 [2026-10-13-forbidden-tool-grouping-design.md](./2026-10-13-forbidden-tool-grouping-design.md)）
- 关联入口：用户管理 / 角色管理的「权限配置 → 禁用工具与命令」

## 1. 现状与问题

### 1.1 内置候选是前端硬编码常量，且同一份写了两遍

「选择要禁用的工具（全局拉黑）」区的 5 个选项来自前端常量 `availableToolsToForbid`，在 [Users.vue:2848](../../../frontend/src/views/Users.vue#L2848) 和 [Roles.vue:1373](../../../frontend/src/views/Roles.vue#L1373) 各写了一份，内容逐字相同：

```ts
const availableToolsToForbid = [
  { id: "exec_command", ... }, { id: "write_file", ... }, { id: "read_file", ... },
  { id: "search_qa_examples", ... }, { id: "manage_process", ... }
];
```

两处独立维护，改名或新增工具必然漏改一处。

### 1.2 高危内置工具存在没有禁用入口的漏网

运行时拦截按名字匹配，并通过 `AGENTSCOPE_BUILTIN_TOOL_ALIASES`（[registry.py:95](../../../app/services/ai/tools/registry.py#L95)）做双向别名扩展，别名表实际覆盖 6 类 AgentScope 内置工具：

| 别名组 | 运行时工具名 | 前端是否有禁用入口 |
| --- | --- | --- |
| exec_command / bash / Bash | Bash | ✅ |
| write_file / write / Write | Write | ✅ |
| read_file / read / Read | Read | ✅ |
| edit_file / edit / Edit | Edit | ❌ 无入口 |
| search_text / grep / Grep | Grep | ❌ 无入口 |
| glob_files / glob / Glob | Glob | ❌ 无入口 |

后果是**能力绕过**：管理员禁用了 `write_file`，智能体仍可用 `Edit` 工具对文件做精确字符串替换写入，写文件能力并未封死。`list_process`（[registry.py:141](../../../app/services/ai/tools/registry.py#L141) 的证据表中有它）同样没有入口。

### 1.3 动态区的过滤集合与硬编码列表不一致

动态区「自定义 API 与 MCP 扩展工具禁用」由 `fetchAllSystemTools()` 拉 `/api/portal/tools` 与 `/api/portal/tools/mcp` 后过滤：

```ts
const forbiddenIds = new Set(["exec_command", "write_file", "read_file", "manage_process"]);
```

该集合只有 4 项，比硬编码列表少了 `search_qa_examples`。当前因为 `/api/portal/tools` 只返回 `sys_api_tools` 表的自定义工具、`/api/portal/tools/mcp` 只返回已发布 MCP 工具（[tools.py:24](../../../app/api/portal/endpoints/tools.py#L24)、[tools.py:71](../../../app/api/portal/endpoints/tools.py#L71)），二者都不含内置工具，所以重复项尚未真正暴露；但两处口径不一致本身就是隐患。

### 1.4 已保存但已不在候选列表中的禁用项无法解除

勾选状态直接 `v-model="permissionData.forbidden_tools"`，模板只遍历两个候选列表。若某个禁用项已不在候选内（例如 MCP 工具被下架、发布被撤销），它既不显示、也无法被取消，管理员只能改数据库。

### 1.5 文案与上下文不符

用户页的说明写的是「配置禁用工具后该**智能体**完全无法调用该工具」（[Users.vue:1219](../../../frontend/src/views/Users.vue#L1219)），在用户维度上应为「该用户」；角色页对应文案是正确的（[Roles.vue:484](../../../frontend/src/views/Roles.vue#L484)）。

## 2. 目标与非目标

### 2.1 目标

1. 禁用工具候选清单由**后端唯一维护**，前端不再持有任何工具硬编码。
2. 内置候选补齐 `edit_file`、`search_text`、`glob_files`、`list_process`，消除能力绕过路径。
3. 勾选某个能力时，同组别名一并写入 `forbidden_tools`，数据库里显式可审计。
4. 历史遗留的禁用项可见、可解除。
5. 候选来源与运行时拦截口径由同一份别名表派生，不再可能各自漂移。

### 2.2 非目标

1. 不把全部内置工具（40+，含 `search_knowledge_base`、`get_current_time`、`publish_generated_file` 等普通能力）纳入安全拉黑页。它们属于工具授权范畴，混在一起只会稀释安全页的语义。
2. 不引入后端保存白名单。`forbidden_tools` 继续接受任意字符串，历史数据与外部调用方不受影响。
3. 不改动 `forbidden_commands`（命令关键字）的存储与拦截。
4. 不改数据库表结构，无数据迁移。

## 3. 设计

### 3.1 架构与数据流

后端成为唯一事实来源，前端只负责渲染与写回：

```
GET /api/portal/tools/forbidden-catalog
        │
        ├── 内置候选（9 组，含别名）  ← 从 AGENTSCOPE_BUILTIN_TOOL_ALIASES 派生
        └── 动态候选（自定义 API + 已发布 MCP）
        ↓
ForbiddenToolCatalog.vue（Users.vue / Roles.vue 共用）
        ↓  v-model: string[]（forbidden_tools）
ResourcePermission(resource_type="forbidden_tool")
        ↓  运行时
enforce_tool_forbidden()（tools.py:1650）按名 + 别名扩展 DENY
```

前端删掉 `availableToolsToForbid`、`otherAvailableTools`、`filteredOtherTools`、`fetchAllSystemTools`、`toolSearchQuery` 与对 `/api/portal/tools`、`/api/portal/tools/mcp` 的两次请求。

### 3.2 后端：目录服务

新增 `app/services/ai/tools/forbidden_catalog.py`：

```python
@dataclass(frozen=True)
class ForbiddenToolCandidate:
    id: str                    # 规范 id，写入 forbidden_tools 的那个名字
    label: str                 # 中文名
    description: str
    category: str              # sandbox | file | process | knowledge | api | mcp
    aliases: tuple[str, ...]   # 运行时可命中的同组名字，恒含 id 自身
```

**内置候选（9 组）**：

| 规范 id | 中文名 | 别名（含自身） | category |
| --- | --- | --- | --- |
| `exec_command` | 执行终端命令 | exec_command, bash, Bash | sandbox |
| `write_file` | 写入/修改文件 | write_file, write, Write | file |
| `edit_file` | 编辑文件内容 | edit_file, edit, Edit | file |
| `read_file` | 读取文件内容 | read_file, read, Read | file |
| `search_text` | 检索文件内容 | search_text, grep, Grep | file |
| `glob_files` | 查找文件 | glob_files, glob, Glob | file |
| `manage_process` | 进程管理 | manage_process | process |
| `list_process` | 查看系统进程 | list_process | process |
| `search_qa_examples` | 检索经验库 | search_qa_examples | knowledge |

**别名由别名表派生，不手写**，保证与运行时拦截口径一致：

```python
# 对 target 为 Bash/Write/Edit/Read/Grep/Glob 的组：
#   aliases = {alias for alias, target_ in ALIASES.items() if target_ == target} | {target}
# manage_process / list_process / search_qa_examples 不在别名表内，aliases = (id,)
```

规范 id 选择平台惯用的下划线名（`exec_command` 而非 `Bash`），因为既有配置与 `AgentManagement.vue` 的内置工具清单都用这套名字；而运行时双向别名扩展会保证 `Bash` 同样被拦。

**动态候选**：自定义 API 工具（复用 `SysApiTool` 查询）与已发布 MCP 工具（复用 `/tools/mcp` 的可见性规则：全局 + 当前用户个人），`category` 分别为 `api`、`mcp`，`aliases` 为空元组。

### 3.3 后端：接口契约

`GET /api/portal/tools/forbidden-catalog`，依赖 `require_api_key`（与 `/api/portal/tools` 一致）。

```json
{
  "candidates": [
    {
      "id": "exec_command",
      "label": "执行终端命令",
      "description": "在沙箱中执行 Bash/shell 命令行",
      "category": "sandbox",
      "aliases": ["exec_command", "bash", "Bash"]
    }
  ]
}
```

- 内置候选恒排在动态候选之前，便于前端稳定分区。
- 按 `id` 去重且**内置优先**：若某个动态候选的 `id` 与内置候选相同（防御性处理，正常情况下不会发生），保留内置项并丢弃该动态项。
- 接口只读、幂等，仅返回元数据，不返回任何用户已配置的禁用项——已选项由权限接口负责回显。

### 3.4 前端：共享组件

新增 `frontend/src/components/system/ForbiddenToolCatalog.vue`：

- **Props / Emits**：`modelValue: string[]`、`disabled?: boolean`；`update:modelValue`。
- **分组渲染**：内置候选按 `category` 显示为高危组（红色样式，保留原「选择要禁用的工具（全局拉黑）」标题），`api` / `mcp` 显示为靛蓝色扩展区，保留原搜索框（匹配 `id` / `label` / `description`）。
- **组勾选语义**：`groupSelected = aliases.some(id => selected.has(id))`；勾选时把整组 `aliases` 并入数组，取消时从数组移除整组。这样保存后数据库里显式列出同组全部名字。
- **别名提示**：每组下方显示「同时拦截：bash、Bash」（`aliases` 长度大于 1 时）。
- **历史遗留区**：已选中但不在候选中的 id 归入「其他已禁用项（历史）」，可单独取消勾选；该区只在存在孤儿项时出现。
- 组件自身拉取目录（`onMounted`），失败时在区内显示错误提示并保留孤儿区，保证已配置项仍可解除。

### 3.5 前端：两页接入

- [Users.vue](../../../frontend/src/views/Users.vue)：删除 `availableToolsToForbid`、`otherAvailableTools`、`filteredOtherTools`、`fetchAllSystemTools`、`toolSearchQuery` 及模板中的两个候选区块，替换为 `<ForbiddenToolCatalog v-model="permissionData.forbidden_tools" />`。
- [Roles.vue](../../../frontend/src/views/Roles.vue)：同上。
- 保存链路（`PermissionUpdate.forbidden_tools` → `ResourcePermission(resource_type="forbidden_tool")`）无需改动。

### 3.6 文案修复

- [Users.vue:1219](../../../frontend/src/views/Users.vue#L1219)：「该智能体完全无法调用该工具」→「该用户完全无法调用该工具」。
- 组件内新增说明：勾选内置能力会同时拦截其在沙箱中的等价工具名。

### 3.7 边界与兼容

| 场景 | 行为 |
| --- | --- |
| MCP 工具被下架、发布撤销 | 不在候选内，落入历史区，仍可见可解除 |
| 个人私有 MCP 工具 | 与 `/tools/mcp` 一致：仅本人可见可选 |
| 别名关系未来扩展 | 目录自动跟随别名表，历史配置因运行时双向扩展仍继续生效 |
| 旧客户端提交 `forbidden_tools` | 后端不校验白名单，行为不变 |
| 未登录/无权限 | 接口返回 401（沿用 `require_api_key`） |

## 4. 与智能体配置页的口径关系

平台当前的内置工具名有 **3 份前端硬编码**：

| 位置 | 条目 | 语义 |
| --- | --- | --- |
| [AgentManagement.vue:617](../../../frontend/src/views/AgentManagement.vue#L617) `availableTools` | 30+ 项 | 智能体「允许挂载」 |
| [Users.vue:2848](../../../frontend/src/views/Users.vue#L2848) `availableToolsToForbid` | 5 项 | 用户「全局拉黑」 |
| [Roles.vue:1373](../../../frontend/src/views/Roles.vue#L1373) | 5 项（与用户页逐字相同） | 角色「全局拉黑」 |

对齐结论：

| 维度 | 现状 | 本设计完成后 |
| --- | --- | --- |
| 名字空间 | 智能体页用「配置名」（`read_file` / `write_file` / `exec_command`…），禁用页应用同一套 | 禁用候选的规范 `id` 与智能体页 `availableTools[].name` 同名，9 组高危项均为其子集 |
| 运行时 | 已对齐：`enforce_tool_forbidden` 双向别名扩展，挂载 `Write` 也会被 `write_file` 拦截 | 不变 |
| 覆盖范围 | 不对齐：禁用页缺 `edit_file` / `search_text` / `glob_files` / `list_process` | 补齐这 4 项；智能体页其余 20+ 项普通能力仍不进禁用候选（见 §2.2） |
| 数据来源 | 3 份硬编码 | 禁用页改为后端目录；智能体页本次不动，但目录服务结构可直接复用 |

**后续（不在本次范围）**：把 [AgentManagement.vue:617](../../../frontend/src/views/AgentManagement.vue#L617) 的 `availableTools` 也改为同一目录接口驱动，仅替换数据来源、不改其分组与选择器 UI，从而消除第 3 份硬编码。

## 5. 测试策略

**后端**（`tests/api/test_forbidden_tool_catalog_contract.py`，`no_infrastructure` 标记）：

1. 目录包含 9 组内置候选，且含 `edit_file` / `search_text` / `glob_files` / `list_process`。
2. 每一组 `aliases` 恒含规范 `id`，且与 `AGENTSCOPE_BUILTIN_TOOL_ALIASES` 的对应组**完全一致**（防漂移断言）。
3. 动态候选并入后 `id` 唯一。
4. 运行时一致性：写入规范 `id` 后，别名工具名被 `enforce_tool_forbidden` 判定 DENY。

**前端**（`tests/frontend/test_forbidden_tool_catalog_contract.py`）：两页均使用共享组件、不再出现 `availableToolsToForbid` 与 `fetchAllSystemTools`、组件实现组勾选与历史遗留区、用户页文案为「该用户」。

**验证命令**：`pytest`（后端 + `--confcutdir=tests/frontend`）、`vue-tsc --noEmit`、以及手工在用户/角色页勾选 `exec_command` 后确认保存请求体包含同组别名。

## 6. 影响面

| 项 | 内容 |
| --- | --- |
| 表结构 | 无变更，无迁移 |
| 接口 | 新增 1 个只读接口；`/tools`、`/tools/mcp` 保留不动 |
| 前端 | 新增 1 个组件；Users.vue / Roles.vue 各减少约 40 行脚本与 2 个模板区块 |
| 权限语义 | 无变化，仍按 `forbidden_tools` 名字集合拦截 |
| 部署 | 需重启后端并重建前端静态资源（由用户在控制台执行 `./dev.sh`） |

## 7. 风险与取舍

1. **组勾选使记录数增加**：勾 6 个内置能力会写入约 14 条 `forbidden_tool` 记录。取舍是显式可审计，优于依赖运行时隐式扩展；且 `PermissionSet` 已做大小写去重。
2. **候选范围是产品判断**：只收「执行与数据访问」类高危工具。若日后需要更宽的范围，扩展 §3.2 的候选表即可，前端无需改动。
3. **目录多一次请求**：组件挂载时拉取一次只读目录，相比原先两页各发两次请求（`/tools` + `/tools/mcp`）反而是净减少。

## 8. 未决问题

无。第 3 节所有行为均已明确到可实现、可测试的粒度。
