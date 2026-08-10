-- 黄金报表：列语义快照 + 运行解读快照
ALTER TABLE `portal_saved_reports`
  ADD COLUMN `column_meta` JSON NULL COMMENT '结果列业务语义快照' AFTER `default_params`;

ALTER TABLE `portal_saved_report_runs`
  ADD COLUMN `analysis_snapshot` JSON NULL COMMENT '执行后 AI 解读快照' AFTER `result_snapshot`;
