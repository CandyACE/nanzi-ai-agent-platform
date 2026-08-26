# 固化报表卡片/列表视图切换 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为完整数据门户和右侧数据门户 panel 增加互相独立的卡片/列表视图切换，同时复用现有固化报表操作链路。

**Architecture:** `SavedReportItemCard.vue` 增加 `variant: "card" | "list"`，列表样式仍由同一组件发出运行、详情、更多操作等事件，避免复制业务逻辑。`DataPortalReportSection.vue` 管理完整门户的宽版视图偏好，`DatasetCapabilityMenu.vue` 管理右侧 panel 的紧凑视图偏好；两者使用不同 localStorage key，默认值均为 `card`。

**Tech Stack:** Vue 3 `<script setup>`、TypeScript、Tailwind CSS、localStorage、pytest 前端契约测试、Vite。

---

### Task 1: 写入视图切换与列表布局的失败契约

**Files:**
- Modify: `tests/frontend/test_saved_report_ui_ux_contract.py`
- Test targets: `SavedReportItemCard.vue`, `DataPortalReportSection.vue`, `DatasetCapabilityMenu.vue`

- [ ] **Step 1: 增加契约断言**

在测试文件增加：

```python
def test_saved_report_views_support_wide_and_compact_switchers():
    section = SECTION.read_text(encoding="utf-8")
    panel = DETAIL.read_text(encoding="utf-8")
    card = CARD.read_text(encoding="utf-8")
    assert "reportViewMode" in section
    assert "nanzi_saved_report_portal_view" in section
    assert "切换到卡片视图" in section
    assert "切换到列表视图" in section
    assert ':variant="reportViewMode"' in section
    assert "savedReportViewMode" in panel
    assert "nanzi_saved_report_panel_view" in panel
    assert "切换报表视图" in panel
    assert ':variant="savedReportViewMode"' in panel
    assert 'variant?: "card" | "list"' in card
    assert "variant === 'list'" in card or 'variant === "list"' in card
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest --confcutdir=tests/frontend tests/frontend/test_saved_report_ui_ux_contract.py -q
```

预期：新增断言失败，因为当前组件没有两个视图状态、localStorage key 或列表 variant。

### Task 2: 为共享报表卡片增加 card/list variant

**Files:**
- Modify: `frontend/src/components/chatbi/SavedReportItemCard.vue`

- [ ] **Step 1: 增加 variant prop**

将 props 扩展为：

```ts
const props = withDefaults(defineProps<{
  report: any;
  formatDate: (iso?: string | null) => string;
  variant?: "card" | "list";
}>(), { variant: "card" });
```

- [ ] **Step 2: 增加列表模板分支**

当 `variant === "list"` 时，报表项使用单行 grid：左侧显示标题，第二列显示归属/权限和标签，中部显示最近运行时间，下一列显示运行次数，最右保留运行、详情和更多操作。所有按钮继续使用现有 `emit`、`isDisabled` 和 `@click.stop`；默认 `variant === "card"` 时原卡片模板保持不变。

- [ ] **Step 3: 运行共享卡片契约测试**

```bash
pytest --confcutdir=tests/frontend tests/frontend/test_saved_report_ui_ux_contract.py -q
```

预期：卡片 variant 相关断言通过，父组件切换断言仍失败。

### Task 3: 实现完整数据门户 A 视图切换

**Files:**
- Modify: `frontend/src/components/data-portal/DataPortalReportSection.vue`

- [ ] **Step 1: 增加宽版视图状态**

使用独立 key `nanzi_saved_report_portal_view`，只接受 `card/list`，非法值回退 `card`，并提供：

```ts
const setReportViewMode = (mode: "card" | "list") => {
  reportViewMode.value = mode;
  localStorage.setItem("nanzi_saved_report_portal_view", mode);
};
```

- [ ] **Step 2: 增加 A 方案切换控件**

仅在 `!compact && manage` 的工具栏显示并排按钮，使用 `aria-pressed`、`aria-label="切换到卡片视图"` 和 `aria-label="切换到列表视图"`；点击只改变布局，不重置筛选和分页。

- [ ] **Step 3: 传递 variant**

管理态容器在列表模式使用单列纵向间距，在卡片模式保持现有响应式三列 grid；向 `SavedReportItemCard` 传递 `:variant="reportViewMode"`。compact 首页的只读卡片固定传 `card`。

### Task 4: 实现右侧 panel B 紧凑切换

**Files:**
- Modify: `frontend/src/components/chatbi/DatasetCapabilityMenu.vue`

- [ ] **Step 1: 增加 panel 独立状态**

使用 `nanzi_saved_report_panel_view`，只接受 `card/list`，默认 `card`；切换函数将新值写入该 key，不读取完整门户的 key。

- [ ] **Step 2: 增加 B 方案视图胶囊**

在 panel 固化报表工具栏的新建、放大、刷新按钮旁增加 `shrink-0` 紧凑按钮，标题为 `切换报表视图`，显示当前布局和目标布局；点击只调用 panel 切换函数。

- [ ] **Step 3: 传递 variant 并保持事件链路**

panel 报表列表在 list 模式使用单列紧凑间距，向 `SavedReportItemCard` 传递 `:variant="savedReportViewMode"`；保留 loading、empty、筛选、运行权限以及所有现有事件处理。

### Task 5: 回归、构建与提交

**Files:**
- Verify: `frontend/src/components/chatbi/SavedReportItemCard.vue`
- Verify: `frontend/src/components/data-portal/DataPortalReportSection.vue`
- Verify: `frontend/src/components/chatbi/DatasetCapabilityMenu.vue`
- Modify: `tests/CHECKLIST.md`

- [ ] **Step 1: 跑固化报表和数据门户契约测试**

```bash
pytest --confcutdir=tests/frontend tests/frontend/test_saved_report_ui_ux_contract.py tests/frontend/test_saved_reports_renaming_and_creation_contract.py tests/frontend/test_data_portal_home_contract.py tests/frontend/test_data_portal_report_closure_contract.py -q
```

预期：全部通过。

- [ ] **Step 2: 执行前端构建**

```bash
cd frontend && npm run build
```

预期：`vue-tsc` 和 Vite 构建成功；既有 Browserslist、动态导入和 chunk 体积提示记录为 warning。

- [ ] **Step 3: 更新清单并检查差异**

在 `tests/CHECKLIST.md` 增加本功能记录，运行 `git diff --check` 和 `git status --short`；只 stage 本需求文件，不 stage 工作区中已有的 AI 性能优化改动。

- [ ] **Step 4: 提交本次功能**

```bash
git add frontend/src/components/chatbi/SavedReportItemCard.vue frontend/src/components/chatbi/DatasetCapabilityMenu.vue frontend/src/components/data-portal/DataPortalReportSection.vue tests/frontend/test_saved_report_ui_ux_contract.py tests/CHECKLIST.md docs/superpowers/plans/2026-08-26-saved-report-view-switch.md
git commit -m "feat: 增加固化报表列表视图"
```
