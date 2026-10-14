# 禁用工具目录 v2 分组渲染 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把「禁用工具与命令」的候选列表从两个扁平区块改为「大组 → 来源子组 → 工具卡片」三层结构，支持两级折叠、组头计数与组内全选。

**Architecture:** 后端在 `/portal/tools/forbidden-catalog` 的每个候选上补 `group_key`（稳定聚合键）+ `group`（展示标签），前端不再自行推断归属；前端把「聚合 / 计数 / 组级全选 / 搜索过滤」抽成纯函数 `forbiddenToolGroups.ts`，组件只负责渲染与折叠状态，折叠键为 `group:builtin` / `group:dynamic` 与子组 `group_key`。

**Tech Stack:** FastAPI + SQLAlchemy 2.x async（后端）；Vue 3 + TypeScript + Tailwind（前端）；pytest / `pytest --confcutdir=tests/frontend` / node transpile harness（测试）。

**Spec:** [docs/superpowers/specs/2026-10-13-forbidden-tool-grouping-design.md](../specs/2026-10-13-forbidden-tool-grouping-design.md)

> **仓库约束（必须遵守）**
> - 按 `AGENTS.md`：**Agent 不自行执行 `git commit`**。
> - 本计划**不需要任何迁移**，不改表结构。
> - 不运行 `./dev.sh`、部署脚本或数据库操作。

---

## 文件结构

**Create**
| 文件 | 职责 |
| --- | --- |
| `frontend/src/utils/forbiddenToolGroups.ts` | 聚合 / 计数 / 组级全选 / 搜索过滤纯函数 |
| `tests/api/test_forbidden_tool_catalog_grouping.py` | 后端分组字段映射的契约测试 |
| `tests/frontend/test_forbidden_tool_grouping_behavior.py` | 纯函数的 node harness 行为测试 |
| `tests/frontend/test_forbidden_tool_grouping_contract.py` | 组件接线契约测试 |

**Modify**
| 文件 | 改动 |
| --- | --- |
| `app/services/ai/tools/forbidden_catalog.py` | `ForbiddenToolCandidate` 增 `group_key` / `group`；内置类别标签映射 |
| `app/api/portal/endpoints/tools.py` | 三个来源填充分组字段；响应输出新字段 |
| `frontend/src/components/system/ForbiddenToolCatalog.vue` | 重写为三层结构 + 两级折叠 + 计数 + 全选 |
| `tests/CHECKLIST.md` | 新增一行交付记录 |

---

## Task 1：候选契约补分组字段（后端）

- [ ] `ForbiddenToolCandidate` 增加 `group_key: str` 与 `group: str`（保持 `frozen=True`）。
- [ ] 内置候选：按 `category` 映射中文标签（`sandbox`→沙箱命令、`file`→文件操作、`process`→进程管理、`knowledge`→知识库，其余→其他内置工具），`group_key = f"builtin:{category}"`。
- [ ] 动态候选：API 用 `SysApiTool.group_name`（空→`api:__ungrouped__` / 「自定义 API · 未分组」），MCP 用 `server.server_name`（空→`mcp:__unknown__` / 「MCP · 未知服务」）。
- [ ] `merge_forbidden_tool_candidates` 的「内置优先、同 id 忽略大小写」行为与候选顺序**保持不变**。
- [ ] 接口响应输出 `group_key` / `group`，既有字段与顺序不变。

**测试**：`tests/api/test_forbidden_tool_catalog_grouping.py`（5 项，见 spec §4）。
**验证**：`.venv/bin/python -m pytest -q tests/api/test_forbidden_tool_catalog_grouping.py tests/api/test_forbidden_tool_catalog_contract.py`

## Task 2：抽纯函数模块（前端）

- [ ] 新增 `frontend/src/utils/forbiddenToolGroups.ts`，导出 `groupCandidates` / `groupSelectedCount` / `applyGroupSelection` / `filterSubGroups` 与两个接口类型。
- [ ] 语义严格按 spec §3.4：聚合保序、不产生空组、计数按 `aliases` 命中、全选并集/取消差集且**不修改入参**、过滤对 `group_key`/`group`/`id`/`label`/`description` 大小写不敏感。

**测试**：`tests/frontend/test_forbidden_tool_grouping_behavior.py`（4 项，node harness 直跑纯函数）。
**验证**：`.venv/bin/python -m pytest --confcutdir=tests/frontend -q tests/frontend/test_forbidden_tool_grouping_behavior.py`

## Task 3：组件重写为三层结构（前端）

- [ ] 大组 1「选择要禁用的工具（全局拉黑）」保留搜索框；大组 2「自定义 API 与 MCP 扩展工具禁用」；两者均可折叠。
- [ ] 每个子组：折叠头（`rotate-90` 箭头 + 标题 + `(已选/总数)` + `[全选/取消全选]`）+ 工具卡片栅格。
- [ ] 折叠状态 `ref<Set<string>>`：大组键 `group:builtin` / `group:dynamic`，子组键 `group_key`，空集为默认全展开。
- [ ] 搜索期间强制展开（只读覆盖，不写回集合）；无命中的子组隐藏，大组全无命中则整体隐藏（内置区同样适用）。
- [ ] 去掉大组 2 的 `max-h-[140px]` 内滚动。
- [ ] orphan 区（「其他已禁用项（历史）」）保持独立、不受搜索过滤、不参与大组全选。
- [ ] 视觉与 `AgentVersionEditorDrawer.vue` 的分组头对齐（箭头/计数/全选按钮），保留内置红、扩展靛蓝、orphan amber 三套语义色。

**测试**：`tests/frontend/test_forbidden_tool_grouping_contract.py`（4 项）。
**验证**：`.venv/bin/python -m pytest --confcutdir=tests/frontend -q tests/frontend`

## Task 4：全量验证与记录

- [ ] `.venv/bin/python -m pytest -q tests/services tests/api tests/ai` → 预期只保留 3 项基线既有失败。
- [ ] `.venv/bin/python -m pytest --confcutdir=tests/frontend -q tests/frontend` → 全绿。
- [ ] `cd frontend && node --max-old-space-size=6144 ./node_modules/vue-tsc/bin/vue-tsc.js --noEmit -p tsconfig.app.json` → 67 = 基线，零新增。
- [ ] `tests/CHECKLIST.md` 新增一行（特性 / 文件 / 设计+测试闭环 / 验收状态 / 日期）。
- [ ] 汇报改动的文件、验证数字与「需用户自行执行 `./dev.sh`」提醒。

---

## 执行后修正（实现过程中发现的偏差记录在此）

1. **分组字段是新增契约的一部分**：`ForbiddenToolCandidate` 的两个新字段设为必填（不给默认值），
   因此 v1 测试里两处手工构造补了 `group_key` / `group`。取舍：语义明确优于"空字符串占位"。
2. **后端动态候选由推导式改为显式循环**：需要在构造前解包 `(group_key, group)` 元组，
   推导式里无法同时保持"关键字参数 + 元组解包"的可读性。
3. **前端三处实现取舍**（由实现者提出、复核通过）：
   - 组头计数与「全选」作用于**当前可见（搜索命中）的候选**，与 `AgentVersionEditorDrawer` 的过滤后分组一致——
     避免搜索状态下点全选把全量工具误禁；
   - `filterSubGroups` 粒度为**子组**：组自身或组内任一候选命中即保留整组（不裁剪组内候选），
     让「全选本组」的含义不随搜索漂移；
   - 大组划分仍用既有 `category !== 'api' && !== 'mcp'` 判据而非 `group_key` 前缀，
     这样旧响应没有 `group_key` 时也能正确落进内置/动态大组。
4. **一条 v1 契约断言保真更新**：`test_forbidden_tool_catalog_contract.py` 断言过
   `isGroupSelected` / `toggleGroup` / `group.aliases`；重写后「组」一词专指子组，
   这三个名字会误导，故改名为 `isCandidateSelected` / `toggleCandidate` / `candidate.aliases`（语义不变）并加注释说明。
5. **已知小瑕疵（不修）**：`groupSelectedCount(group, ...)` 只用到 `group.candidates`，
   组件为此用 `asGroup('__selection__', list)` 造壳。更干净的签名是直接接候选数组，
   但会牵动已通过的 4 项行为测试，收益不足，留作后续重构点。
6. **「大组 2 是否保留内滚动」**按 spec §3.2 / §7 的结论执行：去掉 `max-h-[140px]`，长度由子组折叠接管。
