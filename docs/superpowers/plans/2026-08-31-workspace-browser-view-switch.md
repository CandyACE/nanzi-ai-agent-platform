# 工作空间浏览器视图切换 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为工作空间浏览器增加可靠的手动刷新、列表/文件夹视图切换，并替换底部多选按钮的图标，同时保持现有文件操作行为。

**Architecture:** 在现有 `WorkspaceBrowserDrawer.vue` 内增加本地 `viewMode` 状态和共享展示数据的网格模板分支。刷新按钮统一调用现有 `refreshDirectory`，两种视图继续复用现有选择、双击、右键、长按和权限处理函数，不新增后端接口。

**Tech Stack:** Vue 3 `<script setup>`、TypeScript、Tailwind CSS、`@heroicons/vue`、pytest 源码契约测试、vue-tsc。

---

## 文件清单

- Modify: `frontend/src/components/embed/WorkspaceBrowserDrawer.vue` — 图标导入、视图状态、刷新按钮、视图切换和文件夹网格布局。
- Create: `tests/frontend/test_workspace_browser_view_contract.py` — 验证关键 UI/状态/事件契约，避免回归。
- Create: `docs/superpowers/specs/2026-08-31-workspace-browser-view-switch-design.md` — 已批准的设计说明。

### Task 1: 先写前端契约测试并确认测试会失败

**Files:**
- Create: `tests/frontend/test_workspace_browser_view_contract.py`

- [ ] **Step 1: 写覆盖三个需求的失败测试**

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "frontend/src/components/embed/WorkspaceBrowserDrawer.vue"


def test_workspace_browser_uses_semantic_icons_and_refresh_action():
    source = SOURCE.read_text(encoding="utf-8")

    assert "ArrowPathIcon" in source
    assert "XMarkIcon" in source
    assert '@click="refreshDirectory()"' in source
    assert ':disabled="loading"' in source


def test_workspace_browser_exposes_list_and_grid_modes_with_list_default():
    source = SOURCE.read_text(encoding="utf-8")

    assert "type ViewMode = 'list' | 'grid'" in source
    assert "const viewMode = ref<ViewMode>('list')" in source
    assert "切换到列表视图" in source
    assert "切换到文件夹视图" in source


def test_workspace_browser_grid_reuses_display_items_and_existing_interactions():
    source = SOURCE.read_text(encoding="utf-8")

    assert "v-if=\"viewMode === 'grid'\"" in source
    assert "v-for=\"item in paginatedDisplayItems\"" in source
    assert "@dblclick=\"handleDoubleClick(item)\"" in source
    assert "@contextmenu=\"handleItemContextMenu($event, item)\"" in source
    assert "toggleMultiSelect(item)" in source
```

- [ ] **Step 2: 运行测试确认是预期失败**

Run: `pytest tests/frontend/test_workspace_browser_view_contract.py -q`

Expected: FAIL，因为组件当前没有 `ArrowPathIcon`、`viewMode`、文件夹网格模板和对应切换标签。

### Task 2: 实现图标替换、刷新入口和视图状态

**Files:**
- Modify: `frontend/src/components/embed/WorkspaceBrowserDrawer.vue:1-12,62-64,1690-1750,2040-2080`

- [ ] **Step 1: 增加 Heroicons 导入和默认视图状态**

将导入改为包含：

```ts
import {
  ArrowPathIcon,
  ComputerDesktopIcon,
  FolderIcon,
  ListBulletIcon,
  Squares2X2Icon,
  XMarkIcon,
} from '@heroicons/vue/24/outline'

type ViewMode = 'list' | 'grid'
const viewMode = ref<ViewMode>('list')
```

保留现有 `ComputerDesktopIcon`、`FolderIcon` 用途，不修改其他状态初始化。

- [ ] **Step 2: 在搜索框右侧加入刷新按钮**

在现有搜索输入框容器之后、`含子目录` label 之前加入：

```vue
<button
  type="button"
  class="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-gray-200 bg-white text-gray-500 transition-colors hover:border-primary/30 hover:text-primary disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300"
  :disabled="loading || searchLoading"
  title="刷新当前目录"
  aria-label="刷新当前目录"
  @click="refreshDirectory()"
>
  <ArrowPathIcon class="h-4 w-4" :class="{ 'animate-spin': loading }" aria-hidden="true" />
</button>
```

该调用保留 `refreshDirectory` 的 `preserveSearch: true` 行为，并复用现有错误提示。

- [ ] **Step 3: 替换底部多选按钮中的内联 SVG**

将多选关闭状态的 SVG 替换为 `<ListBulletIcon class="h-5 w-5" aria-hidden="true" />`，将开启状态的 X SVG 替换为 `<XMarkIcon class="h-5 w-5" aria-hidden="true" />`。保留按钮的 `title`、`aria-label`、状态 class 和 `toggleMultiSelectMode`。

- [ ] **Step 4: 运行契约测试，确认状态和刷新部分仍按预期失败**

Run: `pytest tests/frontend/test_workspace_browser_view_contract.py -q`

Expected: 刷新和图标断言通过；视图状态/网格断言仍失败，直到 Task 3 完成。

### Task 3: 增加列表/文件夹切换和文件夹网格模板

**Files:**
- Modify: `frontend/src/components/embed/WorkspaceBrowserDrawer.vue:1778-2030`

- [ ] **Step 1: 在文件容器顶部增加视图切换**

在现有表头之前增加工具行：

```vue
<div class="flex items-center justify-end border-b border-gray-100 px-3 py-2 dark:border-gray-800">
  <div class="inline-flex rounded-lg border border-gray-200 bg-white p-0.5 dark:border-gray-700 dark:bg-gray-900" role="group" aria-label="文件视图">
    <button
      type="button"
      class="inline-flex items-center gap-1 rounded-md px-2 py-1 text-[10px] font-bold transition-colors"
      :class="viewMode === 'list' ? 'bg-primary/10 text-primary' : 'text-gray-500 hover:text-primary'"
      title="切换到列表视图"
      aria-label="切换到列表视图"
      @click="viewMode = 'list'"
    >
      <ListBulletIcon class="h-3.5 w-3.5" aria-hidden="true" />
      列表
    </button>
    <button
      type="button"
      class="inline-flex items-center gap-1 rounded-md px-2 py-1 text-[10px] font-bold transition-colors"
      :class="viewMode === 'grid' ? 'bg-primary/10 text-primary' : 'text-gray-500 hover:text-primary'"
      title="切换到文件夹视图"
      aria-label="切换到文件夹视图"
      @click="viewMode = 'grid'"
    >
      <Squares2X2Icon class="h-3.5 w-3.5" aria-hidden="true" />
      文件夹
    </button>
  </div>
</div>
```

- [ ] **Step 2: 仅在列表模式渲染现有表头和行**

在现有表头与列表内容外层增加 `v-if="viewMode === 'list'"`，保留原有 `v-for`、分页按钮和所有事件，不重写列表行为。

- [ ] **Step 3: 增加共享数据源的文件夹网格**

在同一文件容器中增加：

```vue
<div v-else class="flex-1 overflow-y-auto custom-scrollbar p-2 pb-16 min-h-0">
  <div v-if="displayItems.length === 0 && !searchLoading" class="h-full flex flex-col items-center justify-center text-gray-400 py-12 px-4">
    <span class="text-4xl mb-2">{{ isRecursiveListingActive || isSearchActive ? '🔍' : '📂' }}</span>
    <span class="text-xs font-bold">{{ displayEmptyHint }}</span>
  </div>
  <div v-else class="grid grid-cols-2 gap-2 sm:grid-cols-3">
    <div
      v-for="item in paginatedDisplayItems"
      :key="item.path"
      class="group min-w-0 cursor-pointer rounded-xl border border-gray-100 bg-white p-2.5 transition-all hover:border-primary/30 hover:bg-primary/5 dark:border-gray-800 dark:bg-gray-900/40"
      :class="selectedItem?.path === item.path || selectedPaths.has(item.path) || highlightedPath === item.path ? 'border-primary/40 bg-primary/10 ring-1 ring-primary/20' : ''"
      @click="multiSelectMode ? toggleMultiSelect(item) : handleRowClick(item)"
      @dblclick="handleDoubleClick(item)"
      @contextmenu="handleItemContextMenu($event, item)"
      @touchstart.passive="handleTouchStart($event, item)"
      @touchend="handleTouchEnd"
      @touchmove="handleTouchEnd"
    >
      <div class="flex items-start justify-between gap-1">
        <div class="flex h-10 w-10 items-center justify-center rounded-lg text-lg" :class="getRowVisual(item).iconBg">
          {{ getRowVisual(item).icon }}
        </div>
        <input v-if="multiSelectMode" type="checkbox" class="mt-1 rounded border-gray-300 text-primary" :checked="selectedPaths.has(item.path)" @click.stop="toggleMultiSelect(item)">
      </div>
      <div class="mt-2 truncate text-xs font-bold text-gray-700 dark:text-gray-200" :title="resolveItemDisplayName(item)">
        {{ resolveItemDisplayName(item) }}
      </div>
      <div class="mt-1 flex items-center justify-between gap-1 text-[9px] text-gray-400">
        <span class="truncate">{{ item.is_dir ? '文件夹' : formatSize(item.size) }}</span>
        <span v-if="isRecursiveListingActive" class="max-w-[55%] truncate">{{ getItemLocationHint(item.path) }}</span>
      </div>
    </div>
  </div>
</div>
```

实现时沿用组件现有文件大小格式化函数名称；若当前函数名称不同，以组件内已有定义为准，不新增重复格式化逻辑。网格视图只负责布局，权限/菜单/选择继续走现有函数。

- [ ] **Step 4: 运行契约测试确认全部通过**

Run: `pytest tests/frontend/test_workspace_browser_view_contract.py -q`

Expected: PASS。

### Task 4: 类型检查与范围回归

**Files:**
- Modify: `frontend/src/components/embed/WorkspaceBrowserDrawer.vue` only if type check reports an implementation error.

- [ ] **Step 1: 运行前端契约测试**

Run: `pytest tests/frontend/test_workspace_browser_view_contract.py tests/frontend/test_portal_drawers_resizer_contract.py -q`

Expected: PASS；如环境缺少基础依赖，只记录环境错误，不将其视为功能通过。

- [ ] **Step 2: 运行 Vue 类型检查**

Run: `./node_modules/.bin/vue-tsc --noEmit`

Workdir: `frontend`

Expected: PASS，或仅出现修改前已存在且与本功能无关的错误；若出现本次新增模板/导入错误，修正后重跑。

- [ ] **Step 3: 检查 diff 和工作区边界**

Run: `git diff --check -- frontend/src/components/embed/WorkspaceBrowserDrawer.vue tests/frontend/test_workspace_browser_view_contract.py docs/superpowers/specs/2026-08-31-workspace-browser-view-switch-design.md docs/superpowers/plans/2026-08-31-workspace-browser-view-switch.md && git status --short`

Expected: 无空白错误；只出现本需求相关文件和用户原有改动，不自动 stage 或 commit。

- [ ] **Step 4: 汇报未执行的验收**

明确说明未启动服务，未进行真实浏览器、后端接口及“上传文件后点击刷新”的联调验收；提醒用户自行启动服务后验证三个入口。
