-- V17: 独立保存模型推理内容，避免刷新后与回答正文混合
ALTER TABLE "ai_agent_execution_history"
    ADD COLUMN "reasoning_content" TEXT;
