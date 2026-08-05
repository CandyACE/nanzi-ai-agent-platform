# EmbedChat 初始页「我的资源」Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 EmbedChat 空会话欢迎页展示与工作台一致的 6 张「我的资源」统计卡，点击后在 Embed 内打开「我的资源」弹层，复用个人中心同一套面板完成完整管理。

**Architecture:** 统计卡外壳改为可注入 `select` 回调（工作台仍 `router.push`，Embed 打开弹层）。新建 `PersonalResourcesModal`（形态对齐 `ChatSettings`），懒加载 memory/tokens/data/skills/mcp/tasks 面板。记忆从 `PersonalCenter` 抽出为 `PersonalMemoryPanel`；`DataPortalHome` / `TaskCenter` 在 `embedded` 模式下改 emit，由 EmbedChat 关闭弹层后走现有门户/会话 handler。

**Tech Stack:** Vue 3 + TypeScript、现有 `useWorkbenchHome` / `GET /api/portal/workbench/home`、前端契约测试 `pytest --confcutdir=tests/frontend`

**Spec:** `docs/superpowers/specs/2026-08-06-embedchat-personal-resources-design.md`

---

## File map

| File | Responsibility |
|------|----------------|
| Create `frontend/src/constants/personalResources.ts` | 与后端 `PERSONAL_RESOURCE_DEFS` 对齐的静态 6 卡定义（home 失败 fallback） |
| Modify `frontend/src/components/workbench/WorkbenchPersonalResources.vue` | 去掉内置 `router.push`；`emit('select', item)`；补 dark mode |
| Modify `frontend/src/views/PersonalWorkbench.vue` | `@select` → `/dashboard/personal?tab=` |
| Create `frontend/src/components/personal/PersonalMemoryPanel.vue` | 从 PersonalCenter 抽出的记忆 Tab |
| Modify `frontend/src/views/PersonalCenter.vue` | memory Tab 改为挂载 `PersonalMemoryPanel` |
| Modify `frontend/src/views/DataPortalHome.vue` | `embedded` 时不 `router.replace`；导航改 emit |
| Modify `frontend/src/views/TaskCenter.vue` | `embedded` 时隐藏通知跳转；报表跳转改 emit；支持 props 初始视图 |
| Create `frontend/src/components/embed/PersonalResourcesModal.vue` | 「我的资源」弹层 + Tab + 懒加载面板 |
| Modify `frontend/src/components/embed/WelcomeDashboard.vue` | 问候与能力卡之间插入统计条 |
| Modify `frontend/src/views/EmbedChat.vue` | 拉 home、打开弹层、处理 data/tasks emit |
| Create `tests/frontend/test_embed_personal_resources_contract.py` 等 | 契约测试 |
| Modify `tests/CHECKLIST.md` | 登记本变更 |

---

### Task 1: 静态资源 defs + 统计卡解耦路由

**Files:**
- Create: `frontend/src/constants/personalResources.ts`
- Modify: `frontend/src/components/workbench/WorkbenchPersonalResources.vue`
- Modify: `frontend/src/views/PersonalWorkbench.vue`
- Test: `tests/frontend/test_personal_workbench_contract.py`

- [ ] **Step 1: 写失败契约测试（统计卡不再内置 router）**

在 `tests/frontend/test_personal_workbench_contract.py` 追加（按文件现有 `_source` helper；若无则按同目录其它测试复制 Path 读取）：

```python
def test_workbench_personal_resources_emits_select_instead_of_router():
    source = _source("frontend/src/components/workbench/WorkbenchPersonalResources.vue")
    assert 'emit("select"' in source or "emit('select'" in source
    assert 'path: "/dashboard/personal"' not in source
    assert "useRouter" not in source


def test_personal_workbench_wires_resource_select_to_personal_center():
    source = _source("frontend/src/views/PersonalWorkbench.vue")
    assert "WorkbenchPersonalResources" in source
    assert "@select=" in source
    assert 'path: "/dashboard/personal"' in source
```

- [ ] **Step 2: 跑测试确认失败**

```bash
pytest --confcutdir=tests/frontend \
  tests/frontend/test_personal_workbench_contract.py::test_workbench_personal_resources_emits_select_instead_of_router \
  tests/frontend/test_personal_workbench_contract.py::test_personal_workbench_wires_resource_select_to_personal_center -v
```

Expected: FAIL

- [ ] **Step 3: 新增静态 defs**

Create `frontend/src/constants/personalResources.ts`:

```typescript
import type { WorkbenchPersonalResource } from "@/types/workbench"

/** 与 app/services/workbench_home_service.py PERSONAL_RESOURCE_DEFS 对齐 */
export const PERSONAL_RESOURCE_DEFS = [
  { key: "memory", label: "我的记忆", unit: "条", tab: "memory" },
  { key: "tokens", label: "我的 Token", unit: "本月", tab: "tokens" },
  { key: "data", label: "我的数据门户", unit: "份报表", tab: "data" },
  { key: "skills", label: "我的技能", unit: "个", tab: "skills" },
  { key: "mcp", label: "我的 MCP", unit: "个服务", tab: "mcp" },
  { key: "tasks", label: "我的任务", unit: "个", tab: "tasks" },
] as const

export type PersonalResourceTab = (typeof PERSONAL_RESOURCE_DEFS)[number]["tab"]

export function personalResourceFallbackItems(): WorkbenchPersonalResource[] {
  return PERSONAL_RESOURCE_DEFS.map((spec) => ({
    key: spec.key,
    label: spec.label,
    value: 0,
    unit: spec.unit,
    tab: spec.tab,
    status: "error" as const,
  }))
}
```

- [ ] **Step 4: 改 WorkbenchPersonalResources 为 emit**

将组件改为不再 `useRouter`；`@click` → `emit('select', item)`；保留 `displayValue` / `formatTokenCompact`；补 dark mode class（`dark:bg-gray-800/50` 等，对齐 WelcomeDashboard 卡片）。

完整目标脚本：

```vue
<script setup lang="ts">
import { formatTokenCompact } from "@/utils/tokenFormat"
import type { WorkbenchPersonalResource } from "@/types/workbench"

defineProps<{ items: WorkbenchPersonalResource[] }>()

const emit = defineEmits<{
  (e: "select", item: WorkbenchPersonalResource): void
}>()

const displayValue = (item: WorkbenchPersonalResource) => {
  if (item.status === "error") return "--"
  if (item.key === "tokens") return formatTokenCompact(item.value)
  return String(item.value ?? 0)
}
</script>
```

模板按钮：`@click="emit('select', item)"`，并加 dark 样式。

- [ ] **Step 5: PersonalWorkbench 接线**

```typescript
const openPersonalResource = (item: WorkbenchPersonalResource) => {
  router.push({ path: "/dashboard/personal", query: { tab: item.tab } })
}
```

```vue
<WorkbenchPersonalResources
  v-if="payload?.personal_resources?.length"
  :items="payload.personal_resources"
  @select="openPersonalResource"
/>
```

- [ ] **Step 6: 跑测试确认通过**

同 Step 2 命令。Expected: PASS

- [ ] **Step 7: Commit**

中文提交（commit-tree）：`refactor: 工作台资源卡解耦路由并抽出静态 defs`

---

### Task 2: 抽出 PersonalMemoryPanel

**Files:**
- Create: `frontend/src/components/personal/PersonalMemoryPanel.vue`
- Modify: `frontend/src/views/PersonalCenter.vue`
- Test: `tests/frontend/test_personal_memory_panel_contract.py`

- [ ] **Step 1: 写失败契约测试**

```python
from pathlib import Path
import pytest

pytestmark = pytest.mark.no_infrastructure
ROOT = Path(__file__).resolve().parents[2]

def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")

def test_personal_memory_panel_exists_and_is_used_by_personal_center():
    panel = _source("frontend/src/components/personal/PersonalMemoryPanel.vue")
    center = _source("frontend/src/views/PersonalCenter.vue")
    assert "每日摘要" in panel
    assert "会话摘要" in panel
    assert "长期记忆" in panel
    assert "/api/portal/memory/my/" in panel
    assert "PersonalMemoryPanel" in center
```

- [ ] **Step 2: 跑测试确认失败**

```bash
pytest --confcutdir=tests/frontend tests/frontend/test_personal_memory_panel_contract.py -v
```

Expected: FAIL

- [ ] **Step 3: 抽出面板**

1. 将 `PersonalCenter.vue` 中 memory 相关脚本（约 `memoryView` 起至 memory watchers）与 memory 模板块（`v-else-if="activeTab === 'memory'"` 整段及关联 Modal）移入 `PersonalMemoryPanel.vue`。
2. 面板内继续用 `useToast` / `axios`；`onMounted` 自拉取当前子视图数据。
3. PersonalCenter 改为：

```vue
<div v-else-if="activeTab === 'memory'">
  <PersonalMemoryPanel />
</div>
```

4. 删除已搬迁的 memory-only 状态与函数；勿改 info/permissions/notifications 等无关 Tab。

- [ ] **Step 4: 跑测试确认通过**

同 Step 2。Expected: PASS

推荐：`cd frontend && npx vue-tsc --noEmit`

- [ ] **Step 5: Commit**

`refactor: 抽出 PersonalMemoryPanel 供个人中心与 Embed 共用`

---

### Task 3: DataPortalHome / TaskCenter Embed 导航注入

**Files:**
- Modify: `frontend/src/views/DataPortalHome.vue`
- Modify: `frontend/src/views/TaskCenter.vue`
- Test: `tests/frontend/test_embed_personal_resources_nav_contract.py`

- [ ] **Step 1: 写失败契约测试**

```python
def test_data_portal_home_embedded_guards_dashboard_navigation():
    source = _source("frontend/src/views/DataPortalHome.vue")
    assert "embedded" in source
    assert 'emit("open-report"' in source or "emit('open-report'" in source
    assert 'emit("open-conversation"' in source or "emit('open-conversation'" in source
    assert 'emit("open-question"' in source or "emit('open-question'" in source
    assert "if (!props.embedded)" in source or "if (props.embedded)" in source


def test_task_center_embedded_blocks_notifications_dashboard_push():
    source = _source("frontend/src/views/TaskCenter.vue")
    assert "embedded" in source
    assert "openPersonalNotificationSettings" in source
    # 隐藏入口或 toast，不得在 embedded 下无条件 push notifications
    assert "props.embedded" in source or "embedded" in source
```

- [ ] **Step 2: 跑测试确认失败**

```bash
pytest --confcutdir=tests/frontend tests/frontend/test_embed_personal_resources_nav_contract.py -v
```

Expected: FAIL

- [ ] **Step 3: 改造 DataPortalHome**

增加 emits：`open-report` / `open-conversation` / `open-question`。

- `setSection` / `setReportFilter`：仅当 `!props.embedded` 时 `router.replace`
- `openReport` / `openActivity` / `openQuestion`：`embedded` 时 emit，否则保留原 `router.push('/dashboard/chat', …)`
- `embedded` 时：`v-if="!embedded"` 隐藏移动端 `fixed` 底栏，避免弹层内错位

示例：

```typescript
const openReport = (report: DataPortalReportItem) => {
  if (props.embedded) {
    emit("open-report", { report_id: report.id })
    return
  }
  router.push({ path: "/dashboard/chat", query: { dataset_portal: "1", report_id: report.id } })
}
```

- [ ] **Step 4: 改造 TaskCenter**

1. Props 增加 `embedded?: boolean`（保留现有 `personal-only` 命名习惯）；可选 `initialView` / `initialTaskId`，优先于 `route.query`。
2. 通知设置按钮：`v-if="!embedded"` 隐藏（本轮不实现 Embed 通知页）。
3. `openSavedReportTask`：`embedded` 时 `emit('open-report', { report_id, run_id?, detail_tab })`，否则原 `router.push`。
4. `openPersonalNotificationSettings`：若仍保留函数，embedded 早退（防漏调）。

- [ ] **Step 5: 跑测试确认通过**

同 Step 2。Expected: PASS

- [ ] **Step 6: Commit**

`feat: DataPortal/TaskCenter 支持 Embed 导航注入`

---

### Task 4: PersonalResourcesModal 弹层

**Files:**
- Create: `frontend/src/components/embed/PersonalResourcesModal.vue`
- Test: `tests/frontend/test_embed_personal_resources_contract.py`

- [ ] **Step 1: 写失败契约测试（弹层壳）**

```python
def test_personal_resources_modal_shell_and_tabs():
    modal = _source("frontend/src/components/embed/PersonalResourcesModal.vue")
    assert "我的资源" in modal
    assert "defineAsyncComponent" in modal
    assert "PersonalMemoryPanel" in modal
    assert "PersonalTokenUsage" in modal
    assert "DataPortalHome" in modal
    assert "SkillsManagement" in modal
    assert "McpManagement" in modal
    assert "TaskCenter" in modal
    assert "update:visible" in modal
    assert "activeTab" in modal
```

- [ ] **Step 2: 跑测试确认失败**

```bash
pytest --confcutdir=tests/frontend \
  tests/frontend/test_embed_personal_resources_contract.py::test_personal_resources_modal_shell_and_tabs -v
```

Expected: FAIL

- [ ] **Step 3: 实现弹层**

形态对齐 `ChatSettings.vue`：`absolute inset-0 z-50` + 居中卡片 + 遮罩点击关闭。

- Props：`visible: boolean`，`activeTab: PersonalResourceTab`
- Emits：`update:visible`，`update:activeTab`，以及转发 `open-report` / `open-conversation` / `open-question`
- Tab 列表：`PERSONAL_RESOURCE_DEFS`
- 内容区：`defineAsyncComponent` 懒加载六面板
  - memory → `PersonalMemoryPanel`
  - tokens → `PersonalTokenUsage`
  - data → `DataPortalHome` + `embedded` + 事件转发
  - skills → `SkillsManagement` + `personal-only`（prop 名以 PersonalCenter 为准）
  - mcp → `McpManagement` + `personal-only`
  - tasks → `TaskCenter` + `personal-only` + `embedded` + 事件转发
- 尺寸：`w-[min(920px,96vw)] max-h-[85vh]`，内容区 `overflow-y-auto`

- [ ] **Step 4: 跑测试确认通过**

同 Step 2。Expected: PASS

- [ ] **Step 5: Commit**

`feat: 新增 Embed「我的资源」弹层`

---

### Task 5: WelcomeDashboard + EmbedChat 接线

**Files:**
- Modify: `frontend/src/components/embed/WelcomeDashboard.vue`
- Modify: `frontend/src/views/EmbedChat.vue`
- Modify: `tests/frontend/test_embed_personal_resources_contract.py`
- Modify: `tests/CHECKLIST.md`

- [ ] **Step 1: 扩展契约测试**

```python
def test_welcome_dashboard_renders_personal_resources_before_capabilities():
    dashboard = _source("frontend/src/components/embed/WelcomeDashboard.vue")
    assert "WorkbenchPersonalResources" in dashboard
    assert "open-personal-resources" in dashboard
    resources_pos = dashboard.find("open-personal-resources")
    caps_pos = dashboard.find('grid-cols-1 sm:grid-cols-3')
    assert resources_pos != -1 and caps_pos != -1
    assert resources_pos < caps_pos


def test_embed_chat_wires_workbench_home_and_personal_resources_modal():
    embed = _source("frontend/src/views/EmbedChat.vue")
    assert "PersonalResourcesModal" in embed
    assert "useWorkbenchHome" in embed or "/api/portal/workbench/home" in embed
    assert "personalResourceFallbackItems" in embed
    assert "open-personal-resources" in embed or "openPersonalResources" in embed
```

- [ ] **Step 2: 跑测试确认失败**

```bash
pytest --confcutdir=tests/frontend tests/frontend/test_embed_personal_resources_contract.py -v
```

Expected: 新用例 FAIL

- [ ] **Step 3: 改 WelcomeDashboard**

- Props：`personalResources?: WorkbenchPersonalResource[]`
- Emit：`open-personal-resources`（tab: string）
- 在问候块之后、能力卡 `Transition` **之前**：

```vue
<div v-if="personalResources?.length" class="w-full mb-8 sm:mb-10">
  <p class="text-[10px] font-black text-gray-300 uppercase tracking-widest mb-3 px-1">我的资源</p>
  <WorkbenchPersonalResources
    :items="personalResources"
    @select="(item) => emit('open-personal-resources', item.tab)"
  />
</div>
```

- [ ] **Step 4: 改 EmbedChat 接线**

1. 状态：`showPersonalResources`、`personalResourcesTab`；`useWorkbenchHome()`；`welcomePersonalResources` computed（有数据用 API，否则 `personalResourceFallbackItems()`）。
2. 鉴权成功后（与 `loadWelcomeCards` 同类时机）`loadWorkbenchHome()`。
3. WelcomeDashboard：`:personal-resources` + `@open-personal-resources`。
4. 挂载 `PersonalResourcesModal`（与 `ChatSettings` 同级，位于 Embed 根 `relative` 容器内）。
5. Handler **必须先** `showPersonalResources = false`，再复用现有：
   - 报表 → 现有 `openPortalDrawer` / report 深链
   - 会话 → 现有 loadConversation
   - 提问 → fill 输入框或 `handleQuickQuestion`
6. **禁止**复制第二套门户逻辑；在 EmbedChat 内搜索已有符号接线。

- [ ] **Step 5: 跑全套相关契约**

```bash
pytest --confcutdir=tests/frontend \
  tests/frontend/test_embed_personal_resources_contract.py \
  tests/frontend/test_agent_welcome_cards_contract.py \
  tests/frontend/test_personal_workbench_contract.py \
  tests/frontend/test_personal_memory_panel_contract.py \
  tests/frontend/test_embed_personal_resources_nav_contract.py -v
```

Expected: 全部 PASS

- [ ] **Step 6: 更新 CHECKLIST**

在 `tests/CHECKLIST.md` 增加一行：

| EmbedChat 初始页我的资源 | `WelcomeDashboard.vue`, `PersonalResourcesModal.vue`, `WorkbenchPersonalResources.vue`, `PersonalMemoryPanel.vue`, `DataPortalHome.vue`, `TaskCenter.vue`, `EmbedChat.vue`, `test_embed_personal_resources_contract.py` | 空会话展示 6 卡；点击开 Embed「我的资源」弹层；复用个人中心面板；data/tasks 导航注入 | ✅ 契约 | 2026-08-06 |

- [ ] **Step 7: Commit**

`feat: EmbedChat 初始页接入我的资源统计卡与弹层`

---

### Task 6: 手工验收清单

- [ ] 工作台：6 卡点击仍进 `/dashboard/personal?tab=…`
- [ ] Embed 空会话：问候下整排 6 卡，其下仍是能力 3 卡
- [ ] home 失败：卡显示 `--`，仍可点开弹层
- [ ] 记忆 / Token / 技能 / MCP Tab 可操作
- [ ] 数据门户打开报表：先关弹层再开门户
- [ ] 任务打开保存报表：先关弹层再进门户
- [ ] 任务内无通知设置跳转（或仅 toast）
- [ ] 有消息后欢迎页含统计卡消失
- [ ] 暗色主题与窄屏 iframe 可用

---

## Spec coverage self-check

| Spec 要求 | Task |
|-----------|------|
| 空会话 6 卡 + 保留能力卡 | Task 5 |
| 整排布局 / 响应式 grid | Task 1 + 5 |
| 「我的资源」弹层类设置 | Task 4 |
| 复用个人中心面板 | Task 2 + 4 |
| 抽出记忆 | Task 2 |
| data/tasks 去硬跳 + 先关弹层 | Task 3 + 5 |
| notifications Embed 不实现 | Task 3 |
| home 失败 fallback | Task 1 + 5 |
| 懒加载 | Task 4 |
| CHECKLIST | Task 5 Step 6 |

## Type / 事件一致性

- Tab：`PersonalResourceTab`（`constants/personalResources.ts`）
- 卡片：`select` → 工作台 router / Embed `open-personal-resources`
- 弹层：`v-model:visible` + `v-model:activeTab`（模板可用 `active-tab`）
- 子面板：`open-report` / `open-conversation` / `open-question`
