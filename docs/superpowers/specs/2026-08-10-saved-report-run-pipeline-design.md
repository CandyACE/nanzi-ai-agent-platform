# 黄金报表执行解读统一管线设计

**日期：** 2026-08-10  
**状态：** Approved（方案 2）

## 目标

消除会话内「直跑 SQL → 前端再追问解读」的割裂；让字段业务含义可依据；会话与订阅共用同一套 enriched 结果上下文。

## 约束（已确认）

- 质量 + 连贯流程都要（可改存储）
- 执行阶段允许串模型（仅用于解读，不改写 SQL）
- 订阅推送也要模型解读
- 字段元数据：保存快照 + 执行现取覆盖（混合）

## 架构

`SavedReportRunPipeline` 统一编排：

1. 解析参数 → 直跑已存 SQL（免模型，鉴权不变）
2. 解析列语义：元数据现取覆盖快照；成功则可惰性回写 `column_meta`
3. 组装 enriched 上下文（sql / rows / columns / column_labels / original_query / report_title / params / permission_notice）
4. 有 `conversation_id` 时写入 Redis `last_data_result`（含列标签与 original_query）
5. 需要解读时服务端调用 synthesis（会话与订阅共用分析能力）
6. 返回/推送：表格证据 + 解读结论

边界：不做 SQL 生成/改写；深度可视化仍可手动追问并复用 enriched 缓存。

## 存储

### `portal_saved_reports.column_meta` (JSON, nullable)

```json
{
  "version": 1,
  "captured_at": "ISO8601",
  "source": "save_time|execute_refresh",
  "columns": [
    {"name": "cust_cnt", "term": "客户数", "type": "BIGINT", "desc": "", "table_name": ""}
  ]
}
```

### `portal_saved_report_runs.analysis_snapshot` (JSON, nullable)

存 `{ key_findings, analysis, risk_note, generation_mode, ai_status }`，供回看与订阅。

历史报表无快照：首次执行现取并回写，不做批量回填。

## 执行 API

`POST /saved-reports/{id}/execute`：默认 `defer_analysis=true`，只查数并返回表格 / `column_labels` / `run_id`（`analysis_status=deferred`）。

`POST /saved-reports/{id}/analyze`：基于 `run_id` 或 Redis `last_data_result` 二次生成业务解读，写回 run/`last_data_result`。

会话前端：先渲染表 → 再请求 analyze → 同条消息补上解读。

保存时前端从 ChatBI SQL 日志提取 `column_meta`；后端再用 SQL 别名/启发式补齐缺失 term。

## 会话 UX

单条助手消息结构：

1. 黄金报表执行结果表（列头优先显示 term）
2. 「业务解读」小节（服务端 analysis_markdown）
3. 同条消息展示表格 + 业务解读；不再强制附带「深度可视化分析一下」快捷入口（仍可将结果写入 Redis，供用户主动追问时复用）

失败策略：SQL 失败仍报错；解读失败只降级为「仅表格 + 提示可手动解读」，不阻断执行成功。

## 测试

- column_meta 合并：现取覆盖快照、现取失败回退快照
- execute 响应含 labels；auto 模式含 analysis 字段
- Redis payload 含 original_query / column_labels
- 前端契约：不再自动 `handleQuickQuestion` 黄金报表解读；渲染 `analysis_markdown`
- digest：带 term 的列名进入 AI prompt / 展示
