# 固化报表动态参数快捷插入实施计划

> **For agentic workers:** 本计划在当前会话内按测试先行执行，不自动提交代码。

**目标：** 在固化报表 SQL 编辑器中提供日期、日期时间、月份参数快捷插入，并让保存、试跑、运行参数三条链路使用同一套参数化 SQL 模板。

**架构：** 前端将编辑器内容作为 `sql_template` 保存，依据 SQL 中的受支持占位符生成 `params_schema` 和默认参数；试跑前将占位符渲染为默认日期/月值后调用现有预览接口。运行端继续使用现有 `param_sql`、`date_range`、`month_range` 合同。

**技术栈：** Vue 3 + TypeScript + Tailwind CSS、FastAPI/Pydantic、pytest 前端契约测试。

---

### 任务 1：补充失败契约测试

**文件：**
- 修改：`tests/frontend/test_data_portal_report_closure_contract.py`
- 测试目标：`frontend/src/components/data-portal/DataPortalReportCreateModal.vue`

- [x] 添加数据集中文名与物理名组合展示的断言。
- [x] 添加 SQL 参数快捷按钮、光标插入、日期/月份占位符、参数化保存字段和默认参数的断言。
- [x] 添加试跑使用渲染后 SQL、编辑参数化报表优先读取 `sql_template` 的断言。
- [x] 运行前端契约测试确认新增断言在实现前失败，随后验证通过。

### 任务 2：实现参数识别、光标插入和预览渲染

**文件：**
- 修改：`frontend/src/components/data-portal/DataPortalReportCreateModal.vue`

- [x] 增加 SQL 编辑器引用和 `insertSqlFragment`，在光标位置插入单个占位符或条件片段，并恢复光标位置。
- [x] 增加受支持参数识别：日期/日期时间参数归为 `date_range`，月份参数归为 `month_range`；混用两种范围或出现未知占位符时阻止试跑/保存并给出提示。
- [x] 增加默认预览值渲染，使试跑请求发送具体 SQL，不把 `{{...}}` 直接交给数据源执行。
- [x] 编辑已有参数化报表时优先加载 `report.sql_template`，并保留未改变参数合同的默认参数。

### 任务 3：实现 SQL 编辑器快捷按钮和帮助说明

**文件：**
- 修改：`frontend/src/components/data-portal/DataPortalReportCreateModal.vue`

- [x] 在 SQL 标题旁增加 `?` 帮助按钮，说明只读查询、占位符写法、试跑行为和当前不支持任意自定义参数。
- [x] 增加开始/结束日期、开始/结束时间、开始/结束月份和日期/月份条件片段按钮。
- [x] 数据集下拉项显示 `#ID - 中文名称（物理名称）`，无中文名称时回退为物理名称。

### 任务 4：接通参数化保存并回归验证

**文件：**
- 修改：`frontend/src/components/data-portal/DataPortalReportCreateModal.vue`

- [x] 根据占位符生成 `mode: param_sql`、`sql_template`、`params_schema`、`default_params`；无参数时保持 `static_sql` 兼容行为。
- [x] 增加后端保存边界的未知占位符校验，避免绕过前端保存运行时必失败的报表。
- [x] 运行前端契约测试、`vue-tsc --noEmit`、后端目标文件语法检查，并执行本次文件的 `git diff --check`。
- [x] 检查工作区差异，未覆盖其他元数据、指标或门户改动；完整前端构建仍受既有 `SmartMetricModal.vue` 类型错误阻断。
