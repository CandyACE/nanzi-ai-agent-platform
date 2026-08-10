-- 黄金报表：列语义快照 + 运行解读快照
ALTER TABLE portal_saved_reports
  ADD COLUMN IF NOT EXISTS column_meta JSON NULL;

COMMENT ON COLUMN portal_saved_reports.column_meta IS '结果列业务语义快照';

ALTER TABLE portal_saved_report_runs
  ADD COLUMN IF NOT EXISTS analysis_snapshot JSON NULL;

COMMENT ON COLUMN portal_saved_report_runs.analysis_snapshot IS '执行后 AI 解读快照';
