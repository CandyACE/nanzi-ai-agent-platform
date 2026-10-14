# 禁用工具目录（后端接口驱动）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把用户/角色「禁用工具」候选列表从前端硬编码改为后端目录接口驱动，补齐 `edit_file`/`search_text`/`glob_files`/`list_process`，并让勾选写入整组运行时别名。

**Architecture:** 后端新增纯逻辑目录模块（内置 9 组高危候选，别名从 `AGENTSCOPE_BUILTIN_TOOL_ALIASES` 派生）+ 一个只读合并接口；前端新增共享组件 `ForbiddenToolCatalog.vue`，Users.vue / Roles.vue 删除各自的硬编码常量与两次 `/tools` 请求后接入该组件。不引入保存白名单，无表结构变更。

**Tech Stack:** Python 3.11 / FastAPI / pytest（含 `no_infrastructure` 纯逻辑测试）、Vue 3 + TypeScript + Vite + Tailwind CSS 3、`vue-tsc --noEmit` 类型检查、pytest 源码契约测试。

**设计依据:** [docs/superpowers/specs/2026-10-13-forbidden-tool-catalog-design.md](../specs/2026-10-13-forbidden-tool-catalog-design.md)

**提交约定:** 本项目由用户决定提交时机，**执行者不要运行 `git commit`**。每个任务末尾给出建议的 commit message 草稿供用户使用。

---

## 文件结构

| 文件 | 责任 |
| --- | --- |
| `app/services/ai/tools/forbidden_catalog.py`（新建） | 内置候选定义、别名派生、内置优先合并。纯逻辑，无 DB 依赖 |
| `app/api/portal/endpoints/tools.py`（修改） | 抽出 MCP 可见性查询供两处复用；新增 `GET /forbidden-catalog` |
| `tests/services/ai/test_forbidden_tool_catalog.py`（新建） | 目录纯逻辑测试（别名一致性、合并去重） |
| `tests/api/test_forbidden_tool_catalog_api_contract.py`（新建） | 端点结构契约（内置优先、动态并入、去重） |
| `frontend/src/components/system/ForbiddenToolCatalog.vue`（新建） | 候选渲染、组勾选、搜索、历史遗留区 |
| `frontend/src/views/Users.vue`（修改） | 接入组件、删除硬编码与两次请求、修文案 |
| `frontend/src/views/Roles.vue`（修改） | 接入组件、删除硬编码与两次请求 |
| `tests/frontend/test_forbidden_tool_catalog_contract.py`（新建） | 两页共用组件、无硬编码残留、文案修正 |

---

### Task 1: 后端目录纯逻辑模块

**Files:**
- Create: `app/services/ai/tools/forbidden_catalog.py`
- Test: `tests/services/ai/test_forbidden_tool_catalog.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/services/ai/test_forbidden_tool_catalog.py`：

```python
"""禁用工具目录：内置候选与运行时别名必须同源、同口径。"""

import pytest

from app.services.ai.tools import forbidden_catalog
from app.services.ai.tools.registry import AGENTSCOPE_BUILTIN_TOOL_ALIASES


pytestmark = pytest.mark.no_infrastructure

EXPECTED_BUILTIN_IDS = (
    "exec_command",
    "write_file",
    "edit_file",
    "read_file",
    "search_text",
    "glob_files",
    "manage_process",
    "list_process",
    "search_qa_examples",
)


def test_builtin_catalog_covers_all_high_risk_execution_tools():
    ids = tuple(candidate.id for candidate in forbidden_catalog.BUILTIN_FORBIDDEN_TOOL_CANDIDATES)

    assert ids == EXPECTED_BUILTIN_IDS


def test_builtin_candidate_aliases_always_contain_its_own_id():
    for candidate in forbidden_catalog.BUILTIN_FORBIDDEN_TOOL_CANDIDATES:
        assert candidate.id in candidate.aliases


def test_builtin_candidate_aliases_match_runtime_alias_table():
    """目录别名必须与运行时别名表完全一致，避免出现禁不掉的缺口。"""
    for candidate in forbidden_catalog.BUILTIN_FORBIDDEN_TOOL_CANDIDATES:
        expected = {
            alias
            for alias, target in AGENTSCOPE_BUILTIN_TOOL_ALIASES.items()
            if target == AGENTSCOPE_BUILTIN_TOOL_ALIASES.get(candidate.id)
        }
        if not expected:
            # 不在别名表中的平台工具：只允许包含自身
            assert candidate.aliases == (candidate.id,)
            continue
        expected.add(candidate.id)
        assert set(candidate.aliases) == expected


def test_builtin_catalog_categories_are_high_risk_execution_scoped():
    categories = {candidate.category for candidate in forbidden_catalog.BUILTIN_FORBIDDEN_TOOL_CANDIDATES}

    assert categories == {"sandbox", "file", "process", "knowledge"}


def test_merge_keeps_builtin_first_and_drops_duplicate_dynamic_ids():
    builtin = forbidden_catalog.BUILTIN_FORBIDDEN_TOOL_CANDIDATES[:1]
    dynamic = [
        forbidden_catalog.ForbiddenToolCandidate(
            id="exec_command", label="重复项", description="", category="api", aliases=("exec_command",)
        ),
        forbidden_catalog.ForbiddenToolCandidate(
            id="crm:query", label="CRM 查询", description="", category="mcp", aliases=("crm:query",)
        ),
    ]

    merged = forbidden_catalog.merge_forbidden_tool_candidates(builtin, dynamic)

    assert [candidate.id for candidate in merged] == ["exec_command", "crm:query"]
    assert merged[0].label == builtin[0].label
```

- [ ] **Step 2: 运行测试确认失败**

Run: `.venv/bin/python -m pytest tests/services/ai/test_forbidden_tool_catalog.py -q`
Expected: FAIL/ERROR，报 `ModuleNotFoundError: No module named 'app.services.ai.tools.forbidden_catalog'`

- [ ] **Step 3: 实现目录模块**

创建 `app/services/ai/tools/forbidden_catalog.py`：

```python
"""禁用工具目录：内置高危工具候选（含运行时别名）的唯一来源。

设计口径见 docs/superpowers/specs/2026-10-13-forbidden-tool-catalog-design.md：
候选只覆盖执行与沙箱数据访问类工具，别名从 AGENTSCOPE_BUILTIN_TOOL_ALIASES
派生，保证目录与运行时拦截永远同源。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.services.ai.tools.registry import AGENTSCOPE_BUILTIN_TOOL_ALIASES


@dataclass(frozen=True)
class ForbiddenToolCandidate:
    """一个可禁用工具组；aliases 恒包含 id 自身，其余为运行时可命中的等价名。"""

    id: str
    label: str
    description: str
    category: str
    aliases: tuple[str, ...]


# (规范 id, 中文名, 描述, 分类, 运行时别名组 target 或 None)
_BUILTIN_FORBIDDEN_TOOL_SPECS: tuple[tuple[str, str, str, str, str | None], ...] = (
    (
        "exec_command",
        "执行终端命令 (exec_command)",
        "在沙箱中执行 Bash/shell 命令行",
        "sandbox",
        "Bash",
    ),
    (
        "write_file",
        "写入/修改文件 (write_file)",
        "对沙箱目录物理写入或修改代码文件",
        "file",
        "Write",
    ),
    (
        "edit_file",
        "编辑文件内容 (edit_file)",
        "在沙箱文件中做精确字符串替换，要求先读取目标文件",
        "file",
        "Edit",
    ),
    (
        "read_file",
        "读取文件内容 (read_file)",
        "读取沙箱工作目录中的文本或源代码",
        "file",
        "Read",
    ),
    (
        "search_text",
        "检索文件内容 (search_text)",
        "基于 ripgrep 搜索沙箱文件内容",
        "file",
        "Grep",
    ),
    (
        "glob_files",
        "查找文件 (glob_files)",
        "按 glob 模式查找沙箱中的文件",
        "file",
        "Glob",
    ),
    (
        "manage_process",
        "进程管理 (manage_process)",
        "查看或终止沙箱中的系统进程",
        "process",
        None,
    ),
    (
        "list_process",
        "查看系统进程 (list_process)",
        "列出当前系统进程及 CPU、内存占用",
        "process",
        None,
    ),
    (
        "search_qa_examples",
        "检索经验库 (search_qa_examples)",
        "检索历史问答优质案例及 SQL",
        "knowledge",
        None,
    ),
)


def _aliases_for(spec_id: str, alias_target: str | None) -> tuple[str, ...]:
    """规范 id 恒排首位，其余同组别名按字母序，保证输出稳定可测。"""
    if alias_target is None:
        return (spec_id,)
    members = {
        spec_id,
        alias_target,
        *(alias for alias, target in AGENTSCOPE_BUILTIN_TOOL_ALIASES.items() if target == alias_target),
    }
    return tuple(sorted(members, key=lambda name: (name != spec_id, name)))


BUILTIN_FORBIDDEN_TOOL_CANDIDATES: tuple[ForbiddenToolCandidate, ...] = tuple(
    ForbiddenToolCandidate(
        id=spec_id,
        label=label,
        description=description,
        category=category,
        aliases=_aliases_for(spec_id, alias_target),
    )
    for spec_id, label, description, category, alias_target in _BUILTIN_FORBIDDEN_TOOL_SPECS
)


def merge_forbidden_tool_candidates(
    builtin: Iterable[ForbiddenToolCandidate],
    dynamic: Iterable[ForbiddenToolCandidate],
) -> list[ForbiddenToolCandidate]:
    """内置优先合并：内置候选恒排在前，同 id（忽略大小写）时保留内置项。"""
    merged: list[ForbiddenToolCandidate] = []
    seen: set[str] = set()
    for candidate in (*builtin, *dynamic):
        key = str(candidate.id).strip().casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(candidate)
    return merged
```

- [ ] **Step 4: 运行测试确认通过**

Run: `.venv/bin/python -m pytest tests/services/ai/test_forbidden_tool_catalog.py -q`
Expected: `5 passed`

- [ ] **Step 5: 建议 commit（不要执行）**

```bash
git add app/services/ai/tools/forbidden_catalog.py tests/services/ai/test_forbidden_tool_catalog.py
git commit -m "feat(mcp): 新增禁用工具目录（内置高危候选与运行时别名同源）"
```

---

### Task 2: 只读目录接口

**Files:**
- Modify: `app/api/portal/endpoints/tools.py`（MCP 查询抽取 + 新端点）
- Test: `tests/api/test_forbidden_tool_catalog_api_contract.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/api/test_forbidden_tool_catalog_api_contract.py`：

```python
"""禁用工具目录接口：内置优先、动态并入、按 id 去重。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.portal.endpoints import tools as tools_endpoint


pytestmark = pytest.mark.no_infrastructure


def _db_with(api_tools, mcp_tools):
    """按调用顺序依次返回自定义 API 工具与 MCP 工具的结果集。"""
    db = MagicMock()
    db.execute = AsyncMock(
        side_effect=[
            SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: api_tools)),
            SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: mcp_tools)),
        ]
    )
    return db


@pytest.mark.asyncio
async def test_catalog_endpoint_returns_builtin_first_then_dynamic_candidates():
    api_tool = SimpleNamespace(name="fetch_weather", description="天气查询", group_name="外部服务")
    mcp_tool = SimpleNamespace(
        tool_name="crm:query",
        tool_description="CRM 查询",
        server=SimpleNamespace(server_name="CRM", scope="global"),
    )

    response = await tools_endpoint.list_forbidden_tool_catalog(
        _db_with([api_tool], [mcp_tool]),
        {"role": "admin", "user_id": 1},
    )

    ids = [candidate["id"] for candidate in response["candidates"]]
    assert ids[0] == "exec_command"
    assert ids[-2:] == ["fetch_weather", "crm:query"]
    assert response["candidates"][0]["aliases"] == ["exec_command", "Bash", "bash"]


@pytest.mark.asyncio
async def test_catalog_endpoint_keeps_builtin_entry_when_dynamic_id_collides():
    api_tool = SimpleNamespace(name="read_file", description="同名自定义工具", group_name=None)

    response = await tools_endpoint.list_forbidden_tool_catalog(
        _db_with([api_tool], []),
        {"role": "admin", "user_id": 1},
    )

    read_file_entries = [
        candidate for candidate in response["candidates"] if candidate["id"] == "read_file"
    ]
    assert len(read_file_entries) == 1
    assert read_file_entries[0]["category"] == "file"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `.venv/bin/python -m pytest tests/api/test_forbidden_tool_catalog_api_contract.py -q`
Expected: FAIL，报 `AttributeError: module 'app.api.portal.endpoints.tools' has no attribute 'list_forbidden_tool_catalog'`

- [ ] **Step 3: 抽取 MCP 可见性查询**

修改 `app/api/portal/endpoints/tools.py`：把 `/mcp` 端点里的查询与映射抽成模块级函数，端点改为调用它（行为不变）。

```python
def _visible_published_mcp_tool_stmt(user: Dict[str, Any]):
    """已发布且可用的 MCP 工具：平台公共 + 当前登录用户的个人私有服务。"""
    from sqlalchemy.orm import joinedload

    current_user_id = user.get("user_id") if user.get("user_id") is not None else user.get("id")
    try:
        current_user_id = int(current_user_id) if current_user_id is not None else None
    except Exception:
        pass

    global_cond = or_(McpServer.scope == "global", McpServer.scope.is_(None))
    personal_cond = and_(McpServer.scope == "personal", McpServer.user_id == current_user_id)

    return (
        select(McpToolCache)
        .join(McpToolCache.server)
        .options(joinedload(McpToolCache.server))
        .where(
            McpToolCache.is_published == True,  # noqa: E712 - 与既有查询写法一致
            McpToolCache.is_available == True,  # noqa: E712
            McpServer.enabled_status == 1,
            or_(global_cond, personal_cond),
        )
    )


async def _list_visible_published_mcp_tools(db: AsyncSession, user: Dict[str, Any]):
    result = await db.execute(_visible_published_mcp_tool_stmt(user))
    return result.scalars().all()
```

同时把 `list_published_mcp_tools`（`/mcp` 端点）的函数体替换为：

```python
@router.get("/mcp", response_model=List[Dict[str, Any]])
async def list_published_mcp_tools(
    db: AsyncSession = Depends(get_db_session),
    user: Dict = Depends(require_api_key),
):
    """列出已发布的 MCP 工具：包含平台公共 MCP 工具，以及当前登录用户自己创建的个人私有 MCP 工具。"""
    tools = await _list_visible_published_mcp_tools(db, user)

    return [
        {
            "id": t.id,
            "name": t.tool_name,
            "description": t.tool_description,
            "server_name": t.server.server_name if t.server else "Unknown",
            "server_remark": (t.server.remark if t.server else None) or None,
            "scope": t.server.scope if (t.server and t.server.scope) else "global",
            "parameter_schema": json.loads(t.parameter_schema or "{}")
        } for t in tools
    ]
```

注意：文件顶部需要 `from sqlalchemy import select, or_, and_`（若原先在函数内 import，则移到顶部；`joinedload` 保持在函数内或用 `from sqlalchemy.orm import joinedload` 顶部导入）。

- [ ] **Step 4: 新增目录端点**

在 `app/api/portal/endpoints/tools.py` 顶部补充导入：

```python
from app.services.ai.tools.forbidden_catalog import (
    BUILTIN_FORBIDDEN_TOOL_CANDIDATES,
    ForbiddenToolCandidate,
    merge_forbidden_tool_candidates,
)
```

并在文件末尾新增端点：

```python
@router.get("/forbidden-catalog", response_model=Dict[str, Any])
async def list_forbidden_tool_catalog(
    db: AsyncSession = Depends(get_db_session),
    user: Dict = Depends(require_api_key),
):
    """返回可禁用的工具候选：内置高危工具（含运行时别名）+ 自定义 API 与已发布 MCP 工具。

    只读、幂等；不返回任何用户已配置的禁用项（已选项由权限接口回显）。
    """
    api_tools = (await db.execute(select(SysApiTool).order_by(SysApiTool.created_at.desc()))).scalars().all()
    mcp_tools = await _list_visible_published_mcp_tools(db, user)

    dynamic_candidates = [
        ForbiddenToolCandidate(
            id=str(tool.name),
            label=str(tool.name),
            description=str(tool.description or "自定义 API 工具"),
            category="api",
            aliases=(str(tool.name),),
        )
        for tool in api_tools
        if str(tool.name or "").strip()
    ]
    dynamic_candidates.extend(
        ForbiddenToolCandidate(
            id=str(tool.tool_name),
            label=str(tool.tool_name),
            description=str(tool.tool_description or "MCP 注册工具"),
            category="mcp",
            aliases=(str(tool.tool_name),),
        )
        for tool in mcp_tools
        if str(tool.tool_name or "").strip()
    )

    merged = merge_forbidden_tool_candidates(
        BUILTIN_FORBIDDEN_TOOL_CANDIDATES,
        dynamic_candidates,
    )
    return {
        "candidates": [
            {
                "id": candidate.id,
                "label": candidate.label,
                "description": candidate.description,
                "category": candidate.category,
                "aliases": list(candidate.aliases),
            }
            for candidate in merged
        ]
    }
```

- [ ] **Step 5: 运行测试确认通过**

Run: `.venv/bin/python -m pytest tests/api/test_forbidden_tool_catalog_api_contract.py tests/api/test_mcp_echo_server_api_contract.py -q`
Expected: 全部 PASS（含既有 `/mcp` 端点回归）

- [ ] **Step 6: 建议 commit（不要执行）**

```bash
git add app/api/portal/endpoints/tools.py tests/api/test_forbidden_tool_catalog_api_contract.py
git commit -m "feat(portal): 新增禁用工具目录只读接口并复用 MCP 可见性查询"
```

---

### Task 3: 前端共享组件

**Files:**
- Create: `frontend/src/components/system/ForbiddenToolCatalog.vue`

- [ ] **Step 1: 创建组件**

```vue
<template>
  <div class="space-y-3">
    <!-- 内置高危工具 -->
    <div class="border border-gray-150 rounded-xl p-3 bg-white">
      <h4 class="text-xs font-bold text-gray-700 mb-2 flex items-center justify-between gap-3 select-none">
        <span class="flex items-center gap-1.5">
          <span class="w-1.5 h-1.5 bg-red-500 rounded-full"></span>
          选择要禁用的工具（全局拉黑）
        </span>
        <input
          v-model="searchQuery"
          type="search"
          placeholder="搜索工具名..."
          class="text-[10px] border border-gray-200 rounded px-2 py-0.5 w-[140px] focus:outline-none focus:border-indigo-500"
        />
      </h4>
      <p v-if="loading" class="text-[10px] text-gray-400">正在加载可禁用工具目录…</p>
      <p v-else-if="loadError" class="text-[10px] text-red-500">{{ loadError }}</p>
      <div v-else class="grid grid-cols-1 sm:grid-cols-2 gap-2">
        <label
          v-for="group in filteredBuiltinGroups"
          :key="group.id"
          class="flex items-start p-2 rounded border bg-white transition-colors"
          :class="disabled ? 'opacity-60 cursor-not-allowed' : 'hover:bg-gray-50 cursor-pointer'"
        >
          <input
            type="checkbox"
            :checked="isGroupSelected(group)"
            :disabled="disabled"
            class="mt-1 h-4 w-4 rounded text-red-600 focus:ring-red-500"
            @change="toggleGroup(group, ($event.target as HTMLInputElement).checked)"
          />
          <div class="ml-2 min-w-0">
            <p class="text-xs sm:text-sm font-bold text-gray-900 truncate">{{ group.label }}</p>
            <p class="text-[9px] text-gray-400 truncate">{{ group.description }}</p>
            <p v-if="group.aliases.length > 1" class="text-[9px] text-red-400 truncate">
              同时拦截：{{ group.aliases.filter((alias) => alias !== group.id).join('、') }}
            </p>
          </div>
        </label>
      </div>
    </div>

    <!-- 自定义 API 与 MCP 扩展工具 -->
    <div v-show="filteredDynamicGroups.length > 0" class="border border-gray-150 rounded-xl p-3 bg-white">
      <h4 class="text-xs font-bold text-gray-700 mb-2 flex items-center gap-1.5 select-none">
        <span class="w-1.5 h-1.5 bg-indigo-500 rounded-full"></span>
        自定义 API 与 MCP 扩展工具禁用
      </h4>
      <div class="max-h-[140px] overflow-y-auto border border-gray-100 rounded-lg p-2 bg-gray-50 custom-scrollbar grid grid-cols-1 sm:grid-cols-2 gap-1.5">
        <label
          v-for="group in filteredDynamicGroups"
          :key="group.id"
          class="flex items-center p-1.5 rounded border bg-white hover:bg-gray-50 transition-colors cursor-pointer text-xs"
        >
          <input
            type="checkbox"
            :checked="isGroupSelected(group)"
            :disabled="disabled"
            class="h-3.5 w-3.5 rounded text-indigo-600 focus:ring-indigo-500"
            @change="toggleGroup(group, ($event.target as HTMLInputElement).checked)"
          />
          <div class="ml-1.5 min-w-0 flex-1">
            <p class="font-bold text-gray-900 truncate text-[11px] leading-tight">{{ group.label }}</p>
            <p class="text-[9px] text-gray-400 truncate mt-0.5">{{ group.description }}</p>
          </div>
        </label>
      </div>
    </div>

    <!-- 历史遗留：已禁用但已不在目录中的工具，必须仍可解除 -->
    <div v-if="orphanIds.length" class="border border-amber-200 rounded-xl p-3 bg-amber-50/40">
      <h4 class="text-xs font-bold text-amber-700 mb-1.5 flex items-center gap-1.5 select-none">
        <span class="w-1.5 h-1.5 bg-amber-500 rounded-full"></span>
        其他已禁用项（历史）
      </h4>
      <p class="text-[10px] text-amber-600 mb-2">这些工具已不在当前目录中（例如 MCP 工具已下架），取消勾选即可解除禁用。</p>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
        <label
          v-for="orphanId in orphanIds"
          :key="orphanId"
          class="flex items-center p-1.5 rounded border bg-white hover:bg-gray-50 transition-colors cursor-pointer text-xs"
        >
          <input
            type="checkbox"
            checked
            :disabled="disabled"
            class="h-3.5 w-3.5 rounded text-amber-600 focus:ring-amber-500"
            @change="toggleOrphan(orphanId, ($event.target as HTMLInputElement).checked)"
          />
          <p class="ml-1.5 min-w-0 flex-1 font-mono text-[11px] text-gray-700 truncate">{{ orphanId }}</p>
        </label>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import axios from 'axios'

interface ForbiddenToolCandidate {
  id: string
  label: string
  description: string
  category: string
  aliases: string[]
}

const props = withDefaults(defineProps<{ modelValue: string[]; disabled?: boolean }>(), {
  disabled: false,
})

const emit = defineEmits<{ (e: 'update:modelValue', value: string[]): void }>()

const candidates = ref<ForbiddenToolCandidate[]>([])
const loading = ref(false)
const loadError = ref('')
const searchQuery = ref('')

const selectedIds = computed(() => new Set((props.modelValue || []).map((id) => String(id))))
const catalogIds = computed(() => new Set(candidates.value.map((candidate) => candidate.id)))
const builtinGroups = computed(() =>
  candidates.value.filter((candidate) => candidate.category !== 'api' && candidate.category !== 'mcp'),
)
const dynamicGroups = computed(() =>
  candidates.value.filter((candidate) => candidate.category === 'api' || candidate.category === 'mcp'),
)

const filterGroups = (groups: ForbiddenToolCandidate[]) => {
  const query = searchQuery.value.trim().toLowerCase()
  if (!query) return groups
  return groups.filter(
    (group) =>
      group.id.toLowerCase().includes(query)
      || group.label.toLowerCase().includes(query)
      || group.description.toLowerCase().includes(query),
  )
}

const filteredBuiltinGroups = computed(() => filterGroups(builtinGroups.value))
const filteredDynamicGroups = computed(() => filterGroups(dynamicGroups.value))

/** 已选中但已不在目录里的工具：必须可见、可解除。 */
const orphanIds = computed(() =>
  Array.from(selectedIds.value).filter((id) => !catalogIds.value.has(id)),
)

const isGroupSelected = (group: ForbiddenToolCandidate) =>
  group.aliases.some((alias) => selectedIds.value.has(alias))

const toggleGroup = (group: ForbiddenToolCandidate, checked: boolean) => {
  const next = new Set(selectedIds.value)
  group.aliases.forEach((alias) => {
    if (checked) next.add(alias)
    else next.delete(alias)
  })
  emit('update:modelValue', Array.from(next))
}

const toggleOrphan = (id: string, checked: boolean) => {
  const next = new Set(selectedIds.value)
  if (checked) next.add(id)
  else next.delete(id)
  emit('update:modelValue', Array.from(next))
}

const fetchCatalog = async () => {
  loading.value = true
  loadError.value = ''
  try {
    const response = await axios.get('/api/portal/tools/forbidden-catalog')
    candidates.value = Array.isArray(response.data?.candidates) ? response.data.candidates : []
  } catch (error) {
    loadError.value = '可禁用工具目录加载失败，请刷新页面重试。'
  } finally {
    loading.value = false
  }
}

onMounted(fetchCatalog)
</script>
```

- [ ] **Step 2: 类型检查**

Run: `cd frontend && ./node_modules/.bin/vue-tsc --noEmit`
Expected: 无输出（退出码 0）

- [ ] **Step 3: 建议 commit（不要执行）**

```bash
git add frontend/src/components/system/ForbiddenToolCatalog.vue
git commit -m "feat(web): 新增禁用工具目录共享组件（组勾选 + 历史遗留可解除）"
```

---

### Task 4: Users.vue 接入并修文案

**Files:**
- Modify: `frontend/src/views/Users.vue`

- [ ] **Step 1: 模板替换**

把 `frontend/src/views/Users.vue` 中「1. 禁用工具 Checkbox 组」与「1.2 其他自定义与扩展工具禁用」两个 `<div>` 区块（约 1223-1277 行，从 `<!-- 1. 禁用工具 Checkbox 组 -->` 起、到保留注释 `<!-- 2. 禁用 Bash 命令关键字 -->` 之前的 `</div>` 止）整体替换为：

```vue
                      <ForbiddenToolCatalog v-model="permissionData.forbidden_tools" />
```

- [ ] **Step 2: 修文案**

把该文件中的：

```vue
<p class="opacity-80">配置禁用工具后该智能体完全无法调用该工具。配置禁用命令后，当智能体尝试替该用户运行含有敏感词的系统命令时，将被运行时强行拦截。</p>
```

替换为：

```vue
<p class="opacity-80">配置禁用工具后该用户完全无法调用该工具。配置禁用命令后，当智能体尝试替该用户运行含有敏感词的系统命令时，将被运行时强行拦截。</p>
```

- [ ] **Step 3: 删除脚本中的硬编码与动态拉取**

删除以下内容（约在 2848-2895 行）：

```ts
const availableToolsToForbid = [
  { id: "exec_command", name: "执行终端命令 (exec_command)", description: "在沙箱中执行 Bash/shell 命令行" },
  { id: "write_file", name: "写入/修改文件 (write_file)", description: "对沙箱目录物理写入或修改代码文件" },
  { id: "read_file", name: "读取文件内容 (read_file)", description: "读取沙箱工作目录中的文本或源代码" },
  { id: "search_qa_examples", name: "检索经验库 (search_qa_examples)", description: "检索历史问答优质案例及 SQL" },
  { id: "manage_process", name: "进程管理 (manage_process)", description: "查看或终止沙箱中的系统进程" }
];

const otherAvailableTools = ref<any[]>([]);
const toolSearchQuery = ref("");

const filteredOtherTools = computed(() => { /* ... */ });

const fetchAllSystemTools = async () => { /* ... */ };
```

同时在 `onMounted` 中删除对 `fetchAllSystemTools();` 的调用，并在 `<script setup>` 的导入区加上组件导入：

```ts
import ForbiddenToolCatalog from '../components/system/ForbiddenToolCatalog.vue'
```

- [ ] **Step 4: 确认无残留引用**

Run: `grep -n "availableToolsToForbid\|otherAvailableTools\|filteredOtherTools\|fetchAllSystemTools\|toolSearchQuery" frontend/src/views/Users.vue`
Expected: 无输出

- [ ] **Step 5: 类型检查**

Run: `cd frontend && ./node_modules/.bin/vue-tsc --noEmit`
Expected: 无输出（退出码 0）

- [ ] **Step 6: 建议 commit（不要执行）**

```bash
git add frontend/src/views/Users.vue
git commit -m "refactor(web): 用户权限页接入禁用工具目录组件并修正文案"
```

---

### Task 5: Roles.vue 接入

**Files:**
- Modify: `frontend/src/views/Roles.vue`

- [ ] **Step 1: 模板替换**

把「`<!-- 1. 禁用工具 Checkbox 组 -->`」到「`<!-- 2. 禁用 Bash 命令关键字 -->`」之前的两个 `<div>` 区块（约 488-538 行）整体替换为：

```vue
                              <ForbiddenToolCatalog v-model="permissionData.forbidden_tools" />
```

- [ ] **Step 2: 删除脚本中的硬编码与动态拉取**

删除 `const availableToolsToForbid = [...]`、`const otherAvailableTools = ref<any[]>([])`、`const toolSearchQuery = ref("")`、`filteredOtherTools` computed 与 `fetchAllSystemTools`（约 1373-1419 行），删除 `onMounted` 中的 `fetchAllSystemTools()` 调用，并新增组件导入：

```ts
import ForbiddenToolCatalog from '../components/system/ForbiddenToolCatalog.vue'
```

- [ ] **Step 3: 确认无残留引用**

Run: `grep -n "availableToolsToForbid\|otherAvailableTools\|filteredOtherTools\|fetchAllSystemTools\|toolSearchQuery" frontend/src/views/Roles.vue`
Expected: 无输出

- [ ] **Step 4: 类型检查**

Run: `cd frontend && ./node_modules/.bin/vue-tsc --noEmit`
Expected: 无输出（退出码 0）

- [ ] **Step 5: 建议 commit（不要执行）**

```bash
git add frontend/src/views/Roles.vue
git commit -m "refactor(web): 角色权限页接入禁用工具目录组件"
```

---

### Task 6: 前端契约测试与全量验证

**Files:**
- Test: `tests/frontend/test_forbidden_tool_catalog_contract.py`

- [ ] **Step 1: 写契约测试**

创建 `tests/frontend/test_forbidden_tool_catalog_contract.py`：

```python
"""禁用工具目录：两页共用组件、不再硬编码候选清单。"""

from pathlib import Path


USERS = Path("frontend/src/views/Users.vue")
ROLES = Path("frontend/src/views/Roles.vue")
COMPONENT = Path("frontend/src/components/system/ForbiddenToolCatalog.vue")


def test_users_and_roles_share_the_catalog_component():
    for view in (USERS, ROLES):
        source = view.read_text(encoding="utf-8")
        assert "ForbiddenToolCatalog" in source
        assert "availableToolsToForbid" not in source
        assert "fetchAllSystemTools" not in source
        assert "otherAvailableTools" not in source
        assert "toolSearchQuery" not in source


def test_catalog_component_renders_groups_aliases_and_orphans():
    source = COMPONENT.read_text(encoding="utf-8")

    assert "/api/portal/tools/forbidden-catalog" in source
    assert "同时拦截：" in source
    assert "其他已禁用项（历史）" in source
    assert "isGroupSelected" in source
    assert "toggleGroup" in source
    assert "toggleOrphan" in source
    assert "group.aliases" in source


def test_users_page_copy_targets_the_user_not_the_agent():
    source = USERS.read_text(encoding="utf-8")

    assert "配置禁用工具后该用户完全无法调用该工具" in source
    assert "配置禁用工具后该智能体完全无法调用该工具" not in source
```

- [ ] **Step 2: 运行契约测试**

Run: `.venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_forbidden_tool_catalog_contract.py -q`
Expected: `3 passed`

- [ ] **Step 3: 后端全量相关测试**

Run: `.venv/bin/python -m pytest tests/services/ai/test_forbidden_tool_catalog.py tests/api/test_forbidden_tool_catalog_api_contract.py tests/api/test_mcp_user_context_auth.py tests/services/mcp tests/services/ai -q`
Expected: 全部 PASS

- [ ] **Step 4: 前端契约测试全量**

Run: `.venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend -q`
Expected: 全部 PASS（既有 1782 项 + 新增 3 项）

- [ ] **Step 5: 前端类型检查**

Run: `cd frontend && ./node_modules/.bin/vue-tsc --noEmit`
Expected: 无输出（退出码 0）

- [ ] **Step 6: 建议 commit（不要执行）**

```bash
git add tests/frontend/test_forbidden_tool_catalog_contract.py
git commit -m "test(web): 补禁用工具目录前端契约测试"
```

---

## 手工验收（由用户在控制台完成）

1. 重启后端并重建前端（按项目约定由用户执行 `./dev.sh`，执行者不代跑）。
2. 用户管理 → 编辑用户 → 权限配置 → 禁用工具与命令：
   - 内置区应出现 9 项（含「编辑文件内容 (edit_file)」「检索文件内容 (search_text)」「查找文件 (glob_files)」「查看系统进程 (list_process)」）。
   - 勾选「执行终端命令 (exec_command)」应同时显示并写入 `bash`、`Bash`；生成请求体可在浏览器网络面板确认 `forbidden_tools` 含三个名字。
   - 打开一个已配置了历史禁用项（例如已下架 MCP 工具）的用户，应出现「其他已禁用项（历史）」区，取消勾选后保存成功。
   - 文案应为「配置禁用工具后该用户完全无法调用该工具」。
3. 角色管理 → 编辑角色 → 权限配置 → 禁用工具与命令：行为一致。

## 自审记录

- **Spec 覆盖**：spec §3.2/§3.3 → Task 1、2；§3.4 → Task 3；§3.5/§3.6 → Task 4、5；§3.7/§5 → Task 6；§4 的「智能体页后续」不产生任务（已确认非本次范围）。
- **占位符扫描**：无 TBD/TODO；所有代码步骤含完整代码。
- **类型一致性**：`ForbiddenToolCandidate(id, label, description, category, aliases)` 在 Task 1 定义，Task 2 与 Task 3 的 `id/label/description/category/aliases` 字段名与之一致；接口键名 `candidates` 前后一致。
