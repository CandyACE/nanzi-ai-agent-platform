# AI 固化报表编辑器统一 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Execute this plan task-by-task with a test-first red-green-refactor loop. Do not start `./dev.sh` or提交代码。

**Goal:** 让 AI 固化报表的新建/编辑入口与数据门户手动入口共用 `DataPortalReportCreateModal.vue`，统一数据源、SQL 试跑、动态参数和保存校验流程。

**Architecture:** 保留数据门户编辑器作为唯一业务实现；AI 页面只负责准备草稿对象并监听公共编辑器的关闭/保存事件。公共编辑器通过可选的草稿、覆盖层 class/style 和来源提问字段兼容三类入口。固定报表运行链路不改。

**Tech Stack:** Vue 3 `<script setup>`、TypeScript、Tailwind CSS、Axios、pytest 前端静态契约测试、`vue-tsc`。

---

### Task 1: 为统一入口补充失败契约测试

**Files:**
- Create: `tests/frontend/test_saved_report_editor_unification_contract.py`
- Modify: `tests/frontend/test_chat_surface_extraction_contract.py`

- [ ] **Step 1: 写失败测试**

新增静态契约，锁定以下行为：公共编辑器声明 `initialDraft`/`overlayClass`/`overlayStyle`，展示来源提问并使用统一保存事件；`EmbedChat.vue` 和 `AgentDebug.vue` 均导入、渲染 `DataPortalReportCreateModal`，不再渲染 `SavedReportEditorModal`；AI 入口传递当前草稿并监听 `created`。

```python
def test_ai_surfaces_use_data_portal_report_editor():
    for path in ("frontend/src/views/EmbedChat.vue", "frontend/src/views/AgentDebug.vue"):
        source = _read(path)
        assert "import DataPortalReportCreateModal" in source
        assert "<DataPortalReportCreateModal" in source
        assert ':report="saveReportForm"' in source
        assert '@created="handleSavedReportEditorCreated"' in source
        assert "<SavedReportEditorModal" not in source


def test_shared_report_editor_accepts_ai_draft_and_keeps_context_read_only():
    source = _read("frontend/src/components/data-portal/DataPortalReportCreateModal.vue")
    assert "initialDraft?: any | null" in source
    assert "overlayClass?: string" in source
    assert "overlayStyle?: Record<string, string>" in source
    assert "original_query" in source
    assert "来源提问" in source
```

同时把原有 `test_both_chat_surfaces_use_shared_saved_report_dialogs` 改成断言两个页面使用 `DataPortalReportCreateModal`，保留 `SavedReportRunModal` 的共享断言；旧组件文件先保留，避免本次改动扩大到无关清理。

- [ ] **Step 2: 运行测试确认按预期失败**

```bash
pytest --confcutdir=tests/frontend tests/frontend/test_saved_report_editor_unification_contract.py tests/frontend/test_chat_surface_extraction_contract.py -q
```

预期：失败，原因是公共编辑器尚未声明这些 props，两个 AI 页面仍渲染旧编辑器。

### Task 2: 扩展公共编辑器以承接 AI 草稿

**Files:**
- Modify: `frontend/src/components/data-portal/DataPortalReportCreateModal.vue`

- [ ] **Step 1: 扩展输入契约并集中计算当前草稿**

将 props 扩展为：

```ts
const props = defineProps<{
  visible: boolean
  report?: any | null
  initialDraft?: any | null
  overlayClass?: string
  overlayStyle?: Record<string, string>
  scrollbarVariant?: 'embed' | 'debug'
}>()

const activeReport = computed(() => props.report || props.initialDraft || null)
```

编辑态优先使用 `report`，没有编辑 ID 的 AI 草稿使用 `initialDraft`。`resetForm`、标题、保存 URL、参数兼容逻辑全部改读 `activeReport`，避免手动新建的空值行为变化。

- [ ] **Step 2: 让草稿正确初始化数据源、标签、SQL 和参数**

`resetForm(sourceReport)` 使用 `tags` 数组或 `tags_input`，将 `data_source` 保存到 `pendingSourceName`，使用 `sql_template || sql_content` 初始化 SQL；数据源列表加载后优先按 `pendingSourceName` 匹配 `source_key/name`，找不到时才使用现有的首个数据源回退行为。保留当前 `params_schema`/`default_params` 转换，确保 AI 识别出的日期参数和自定义参数可继续编辑。

- [ ] **Step 3: 展示只读来源提问并统一覆盖层**

在描述区域之前增加 `v-if="activeReport?.original_query"` 的“来源提问”只读块，不允许修改或拼接到 SQL。最外层覆盖层合并 `overlayClass` 和 `overlayStyle`，z-index 提升到旧 AI 编辑器同级；滚动容器继续使用公共编辑器滚动样式，`scrollbarVariant` 兼容 ChatBI/Debug 的滚动条宽度。

- [ ] **Step 4: 统一保存读取 activeReport**

保存逻辑使用 `activeReport?.id` 判断 PUT/POST，并用 `activeReport` 读取原 SQL 参数配置；保存成功继续发出 `created` 和 `close`。标题显示“编辑固化报表/新建固化报表”，底部按钮显示“保存修改/创建固化报表”。

- [ ] **Step 5: 运行公共编辑器契约测试**

```bash
pytest --confcutdir=tests/frontend tests/frontend/test_saved_report_editor_unification_contract.py tests/frontend/test_data_portal_report_closure_contract.py -q
```

预期：公共编辑器相关断言通过；AI 页面断言仍失败，直到 Task 3 完成。

### Task 3: 切换 EmbedChat 和 AgentDebug 到公共编辑器

**Files:**
- Modify: `frontend/src/views/EmbedChat.vue`
- Modify: `frontend/src/views/AgentDebug.vue`

- [ ] **Step 1: 统一 AI 草稿形状**

保留现有的名称、描述、标签、原始提问、SQL、参数和数据源推导；编辑态额外保留 `id: report.id`，使公共编辑器执行 PUT；AI 新建草稿不设置 `id`，使公共编辑器执行 POST。

- [ ] **Step 2: 替换旧编辑器模板和导入**

两个页面删除 `SavedReportEditorModal` 导入和模板，改为：

```vue
<DataPortalReportCreateModal
  :visible="showSaveReportModal"
  :report="saveReportForm"
  :overlay-class="saveReportModalOverlayClass"
  :overlay-style="saveReportModalOverlayStyle"
  scrollbar-variant="embed"
  @close="closeSavedReportEditor"
  @created="handleSavedReportEditorCreated"
/>
```

Debug 页面将 `scrollbar-variant` 改为 `debug`。两个页面使用同一个关闭处理函数，清空编辑标记但不改变报表运行状态。

- [ ] **Step 3: 停用旧的直连保存提交路径**

删除或改为不再被模板引用的 `submitSaveReport`，避免 AI 页面绕过公共编辑器的 SQL 试跑和权限预检。公共编辑器成功事件仅负责关闭弹窗；报表列表刷新继续由数据门户自己的 `created` 处理。

- [ ] **Step 4: 运行 AI 入口契约测试**

```bash
pytest --confcutdir=tests/frontend tests/frontend/test_saved_report_editor_unification_contract.py tests/frontend/test_chat_surface_extraction_contract.py -q
```

预期：通过，且仍保留两个页面的 `SavedReportRunModal` 共享断言。

### Task 4: 类型检查和固定报表回归

**Files:**
- Verify: `frontend/src/components/data-portal/DataPortalReportCreateModal.vue`
- Verify: `frontend/src/views/EmbedChat.vue`
- Verify: `frontend/src/views/AgentDebug.vue`
- Verify: `tests/frontend/test_saved_report_editor_unification_contract.py`

- [ ] **Step 1: 运行完整相关前端契约测试**

```bash
pytest --confcutdir=tests/frontend \
  tests/frontend/test_saved_report_editor_unification_contract.py \
  tests/frontend/test_data_portal_report_closure_contract.py \
  tests/frontend/test_saved_reports_renaming_and_creation_contract.py \
  tests/frontend/test_chat_surface_extraction_contract.py \
  tests/frontend/test_dataset_menu_loading_contract.py -q
```

预期：本次相关测试全部通过；工作区已有的其他失败单独记录，不修改无关模块。

- [ ] **Step 2: 运行前端类型检查**

```bash
npm exec -- vue-tsc --noEmit
```

预期：退出码为 0。

- [ ] **Step 3: 检查变更差异**

```bash
git diff --check -- docs/superpowers/specs/2026-08-25-unify-saved-report-editor-design.md docs/superpowers/plans/2026-08-25-unify-saved-report-editor.md frontend/src/components/data-portal/DataPortalReportCreateModal.vue frontend/src/views/EmbedChat.vue frontend/src/views/AgentDebug.vue tests/frontend/test_saved_report_editor_unification_contract.py tests/frontend/test_chat_surface_extraction_contract.py
```

预期：无空白字符错误；不执行 `./dev.sh`、部署或数据库操作。

### Task 5: 试跑动态参数先选择再查询

**Files:**
- Modify: `frontend/src/components/data-portal/DataPortalReportCreateModal.vue`
- Modify: `tests/frontend/test_saved_report_editor_unification_contract.py`

- [ ] **Step 1: 写失败契约**

增加断言，要求公共编辑器包含试跑参数状态、日期/月份范围选项、确认试跑动作，并且 `runTestSql` 在动态参数场景先打开参数弹窗，而不是直接使用固定日期。

```python
assert "showTestParameterModal" in source
assert "testParameterForm" in source
assert "custom_range" in source
assert "custom_month_range" in source
assert "确认试跑" in source
assert "openTestParameterModal" in source
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest --confcutdir=tests/frontend tests/frontend/test_saved_report_editor_unification_contract.py -q
```

预期：失败，因为编辑器当前只有默认日期替换，没有试跑参数弹窗。

- [ ] **Step 3: 实现试跑参数状态和参数渲染**

在公共编辑器中增加与正式运行表单一致的状态：`dateRange/startDate/endDate`、`monthRange/startMonth/endMonth` 和 `customParams`。默认值分别为“本月截至今天”“最近 6 个完整月”和各自配置的默认值。根据 SQL 占位符识别是否需要弹窗；静态 SQL 不弹窗。

将 `buildPreviewSql` 改为接收本次试跑参数，按后端 `_resolve_report_sql` 的规则计算今天、昨天、最近 7 天、本月至今、今年、自定义日期，以及最近 6 个完整月、本年截至本月、自定义月份；自定义文本、数字、下拉参数继续按配置安全转义。

- [ ] **Step 4: 增加试跑参数弹窗并接入查询**

弹窗展示日期范围/月份范围选择和自定义参数控件；选择“自定义”时展示日期或月份输入框；点击“确认试跑”才调用现有 `/api/portal/saved-reports/preview-sql`，继续使用当前数据源、只读 SQL 和权限校验。取消只关闭弹窗，不执行查询。

- [ ] **Step 5: 运行契约和类型检查**

```bash
pytest --confcutdir=tests/frontend tests/frontend/test_saved_report_editor_unification_contract.py tests/frontend/test_data_portal_report_closure_contract.py -q
npm exec -- vue-tsc --noEmit
```

预期：契约测试通过，类型检查退出码为 0。
