# 黄金报表执行解读统一管线 Implementation Plan

> **For agentic workers:** Implement task-by-task. Steps use checkbox syntax.

**Goal:** 会话与订阅共用 enriched 黄金报表执行上下文（列语义 + 服务端解读），去掉前端二次追问。

**Architecture:** `SavedReportColumnMeta` 解析/合并 + execute 后服务端 analysis；digest 消费同一套 labels；前端渲染 `analysis_markdown`。

**Tech Stack:** FastAPI, SQLAlchemy, Redis last_data_result, Vue EmbedChat/AgentDebug, pytest

**Spec:** `docs/superpowers/specs/2026-08-10-saved-report-run-pipeline-design.md`

---

### Task 1: 迁移与模型

**Files:**
- Create: `db-prod/V118-saved-report-column-meta-and-analysis.sql`
- Create: `db-prod-pg/V18-saved-report-column-meta-and-analysis.sql`
- Modify: `app/models/saved_report.py`

- [ ] 报表表加 `column_meta` JSON；run 表加 `analysis_snapshot` JSON
- [ ] ORM 同步字段

### Task 2: 列语义服务

**Files:**
- Create: `app/services/saved_report_column_meta.py`
- Create: `tests/services/test_saved_report_column_meta.py`

- [ ] `build_column_meta_from_result` / `merge_column_meta` / `resolve_column_labels`
- [ ] 复用 `load_column_term_map_for_datasets` + 别名启发
- [ ] 单测：覆盖、回退、空输入

### Task 3: 会话解读服务

**Files:**
- Create: `app/services/saved_report_analysis_service.py`
- Modify: `app/services/saved_report_digest_service.py`（labels 进 snapshot rows / AI prompt）
- Test: `tests/services/test_saved_report_analysis_service.py`

- [ ] `analyze_saved_report_result` → 结构化 JSON + markdown
- [ ] digest `_snapshot_rows` 优先用 `column_labels` / run/report meta
- [ ] `enrich_digest_with_ai` prompt 增加 `original_query`、`column_labels`

### Task 4: 接入 execute 管线

**Files:**
- Modify: `app/api/portal/endpoints/saved_reports.py`
- Test: `tests/api/portal/test_saved_reports.py`（必要时加单测）

- [ ] 保存时可选写入 `column_meta`
- [ ] 执行后 resolve labels、回写 meta、enriched Redis、auto 时 analysis
- [ ] 响应附带 `column_labels` / `analysis` / `analysis_markdown` / `analysis_status`
- [ ] run 写入 `analysis_snapshot`

### Task 5: 前端

**Files:**
- Modify: `frontend/src/views/EmbedChat.vue`
- Modify: `frontend/src/views/AgentDebug.vue`
- Modify: markdown 渲染 helpers（若有 `renderSavedReportDataToMarkdown`）
- Test: frontend contract pytest

- [ ] 去掉自动 `handleQuickQuestion` 业务解读
- [ ] 渲染服务端 `analysis_markdown`；保留深度可视化入口
- [ ] 表格列头尽量用 labels

### Task 6: 回归

- [ ] `pytest tests/services/test_saved_report_column_meta.py tests/services/test_saved_report_analysis_service.py tests/services/test_saved_report_digest_service.py`
- [ ] 相关 portal / frontend contract 测试
