# 固化报表 UI/UX 完整优化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变固化报表 API、权限和订阅业务规则的前提下，统一数据门户与聊天侧固化报表体验，突出运行主流程，补齐结果状态、详情管理和移动端操作闭环。

**Architecture:** 以现有 `SavedReportItemCard` 作为列表卡片唯一视觉基准，新增轻量快捷视图组件承载“最近运行/常用/订阅中”，并将详情抽屉作为管理中心。运行流程继续复用现有预检、执行、分析 API，只优化参数透明度、状态表达和错误降级。

**Tech Stack:** Vue 3、TypeScript、Tailwind CSS 3、现有 axios/组件事件模式、pytest 前端契约测试。

---

### Task 1: 建立 UI/UX 回归契约

**Files:**
- Create: `tests/frontend/test_saved_report_ui_ux_contract.py`
- Test: `frontend/src/components/chatbi/SavedReportItemCard.vue`
- Test: `frontend/src/components/data-portal/DataPortalReportSection.vue`
- Test: `frontend/src/components/chat/SavedReportRunModal.vue`

- [ ] **Step 1: Write the failing contract tests**

```python
def test_saved_report_card_has_text_primary_actions_and_more_menu():
    source = CARD.read_text(encoding="utf-8")
    assert "运行" in source
    assert "详情" in source
    assert "更多操作" in source
    assert "点击打开详情" not in source


def test_report_section_exposes_quick_views_and_shared_filter_semantics():
    source = SECTION.read_text(encoding="utf-8")
    for label in ("最近运行", "常用报表", "订阅中"):
        assert label in source
    assert "共享给我" in source


def test_run_modal_exposes_actual_scope_and_permission_state():
    source = RUN_MODAL.read_text(encoding="utf-8")
    assert "本次查询范围" in source
    assert "实际执行 SQL" in source
    assert "权限预检" in source
```

- [ ] **Step 2: Run the focused contract test and verify it fails**

Run: `pytest --confcutdir=tests/frontend tests/frontend/test_saved_report_ui_ux_contract.py -q`

Expected: FAIL because the current card still uses icon-only actions, the section has no dedicated quick-view row, and the run modal has no explicit actual-scope label.

- [ ] **Step 3: Keep the test assertions limited to user-visible contracts**

Do not assert private Vue implementation details or alter backend response contracts.

### Task 2: Simplify the shared report card and add quick views

**Files:**
- Create: `frontend/src/components/chatbi/SavedReportQuickViews.vue`
- Modify: `frontend/src/components/chatbi/SavedReportItemCard.vue`
- Modify: `frontend/src/components/data-portal/DataPortalReportSection.vue`
- Modify: `frontend/src/components/chatbi/DatasetCapabilityMenu.vue`
- Modify: `frontend/src/components/chatbi/SavedReportBrowseModal.vue`
- Test: `tests/frontend/test_saved_report_ui_ux_contract.py`

- [ ] **Step 1: Add `SavedReportQuickViews` with three computed groups**

The component accepts `reports`, `formatDate`, and emits `select(report)`. It renders at most six items for each of `recent`, `frequent`, and `subscribed`, with a text `运行` button and an empty state. It must not issue API calls; the parent owns execution.

- [ ] **Step 2: Replace the card icon action row with `运行`, `详情`, and `更多操作`**

Keep the existing event names (`execute`, `detail`, `favorite`, `pin`, `share`, `copy`, `delete`, `subscription`) so all existing parents remain compatible. Use a local menu state, close it after an action, add `aria-label`, and remove the long card-level native `title`.

- [ ] **Step 3: Mount quick views in both report surfaces**

Place `SavedReportQuickViews` above the full list in `DataPortalReportSection` and the reports panel in `DatasetCapabilityMenu`. Use the existing in-memory list only. Keep scope controls (`全部/我的/共享给我`) separate from smart views (`最近运行/常用/订阅中`).

- [ ] **Step 4: Reuse the same card in the browse modal without duplicating action semantics**

Preserve the modal’s search, scope, tag, and smart-filter behavior while allowing the shared card to own the visible action hierarchy.

- [ ] **Step 5: Run the focused frontend contract test**

Run: `pytest --confcutdir=tests/frontend tests/frontend/test_saved_report_ui_ux_contract.py -q`

Expected: PASS.

### Task 3: Make the detail drawer the management center

**Files:**
- Modify: `frontend/src/components/chatbi/DatasetCapabilityMenu.vue`
- Modify: `frontend/src/components/chatbi/SavedReportBrowseModal.vue`
- Test: `tests/frontend/test_saved_report_ui_ux_contract.py`

- [ ] **Step 1: Rework the detail header**

Show title, permission/status badge, owner/source summary, last-run time, run count, and a single prominent `运行报表` button. Keep edit/share behind the owner-only `更多操作` menu or existing owner actions.

- [ ] **Step 2: Keep three explicit tabs**

Use `报表概览`, `运行历史`, and owner-only `订阅与共享`. In the overview, show description, Chinese data-source/dataset name when available, tags, parameters, and read-only SQL. In run history, preserve existing result snapshot expansion and add visible duration/row count/error state.

- [ ] **Step 3: Add status-specific empty and error copy**

Use `暂无运行记录`, `暂无订阅`, and actionable retry/error text. Do not collapse permission failures, SQL failures, and AI analysis failures into one generic state.

- [ ] **Step 4: Verify the drawer contract**

Add assertions for `报表概览`, `运行历史`, `订阅与共享`, `运行报表`, and `更多操作`, then run the focused contract test.

### Task 4: Improve parameter execution transparency and responsive behavior

**Files:**
- Modify: `frontend/src/components/chat/SavedReportRunModal.vue`
- Modify: `frontend/src/views/EmbedChat.vue`
- Modify: `frontend/src/views/AgentDebug.vue`
- Modify: `frontend/src/composables/chat/useSavedReportWorkflow.ts`
- Test: `tests/frontend/test_saved_report_ui_ux_contract.py`

- [ ] **Step 1: Show an explicit “本次查询范围” summary**

Derive a human-readable summary from the selected date/month/custom parameters and render it above the SQL preview. Keep the existing preview request as the source of truth for the rendered SQL and permission result.

- [ ] **Step 2: Rename the permission status area**

Use the visible label `权限预检` with states `预检中`, `可运行`, `无权限`, and `待校验`. Keep the primary button disabled when preview is pending or denied.

- [ ] **Step 3: Add compact mobile layout rules**

Use a bottom-aligned action area, full-width primary run button, stacked custom parameters, horizontally scrollable filter rows, and minimum 40px touch targets. Keep SQL preview collapsible on narrow screens.

- [ ] **Step 4: Separate query status from AI analysis status**

Update `composeSavedReportExecuteMarkdown` and the two execution flows so the result always renders as successful query data first. Render analysis as a separate state: `正在生成业务解读`, `业务解读`, or `业务解读暂不可用，可重试`; never replace a successful query result with an execution failure message.

- [ ] **Step 5: Add frontend contract assertions for the state copy**

Assert the source contains `查询成功`, `业务解读`, `重试解读`, and does not use the old one-line fallback as the only visible result state.

### Task 5: Complete verification and handoff

**Files:**
- Test: `tests/frontend/test_saved_report_ui_ux_contract.py`
- Test: existing saved-report API/service tests

- [ ] **Step 1: Run focused frontend contracts**

Run: `pytest --confcutdir=tests/frontend tests/frontend/test_saved_report_ui_ux_contract.py tests/frontend/test_general_message_continue_analysis_contract.py tests/frontend/test_dataset_menu_loading_contract.py -q`

- [ ] **Step 2: Run saved-report backend regression tests**

Run: `venv/bin/python -m pytest -q tests/api/portal/test_saved_reports.py tests/services/test_saved_report_analysis_service.py`

- [ ] **Step 3: Run formatting/diff checks**

Run: `git diff --check`

- [ ] **Step 4: Inspect the final diff and preserve unrelated changes**

Confirm only the planned frontend components/tests and already-owned saved-report transaction fix are included. Do not run `./dev.sh`, deployment scripts, or production database operations; hand deployment to the user.
