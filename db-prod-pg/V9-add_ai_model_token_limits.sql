-- V9: add optional model context and output token limits.
-- NULL keeps the provider/AgentScope default behavior for existing models.

ALTER TABLE "ai_models"
    ADD COLUMN IF NOT EXISTS "context_size" INTEGER NULL,
    ADD COLUMN IF NOT EXISTS "max_output_tokens" INTEGER NULL;

COMMENT ON COLUMN "ai_models"."context_size" IS '模型上下文窗口大小（token）';
COMMENT ON COLUMN "ai_models"."max_output_tokens" IS '单次请求最大输出 token 数';
