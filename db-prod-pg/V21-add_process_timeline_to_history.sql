-- V21: 会话思考卡定稿快照，刷新历史后可回放过程话术与工具步骤
ALTER TABLE "ai_agent_execution_history"
    ADD COLUMN IF NOT EXISTS "process_timeline" JSONB;
