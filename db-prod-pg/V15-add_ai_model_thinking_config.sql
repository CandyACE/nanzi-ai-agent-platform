-- V15: add per-model thinking mode configuration.

ALTER TABLE "ai_models"
    ADD COLUMN IF NOT EXISTS "thinking_enabled" BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS "thinking_only" BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS "allow_disable_thinking" BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS "default_reasoning_effort" VARCHAR(32) NOT NULL DEFAULT 'auto',
    ADD COLUMN IF NOT EXISTS "supported_reasoning_efforts" TEXT NULL;

UPDATE "ai_models"
SET "supported_reasoning_efforts" = '["low","high","max"]'
WHERE "supported_reasoning_efforts" IS NULL OR "supported_reasoning_efforts" = '';

COMMENT ON COLUMN "ai_models"."thinking_enabled" IS '是否启用思考模式';
COMMENT ON COLUMN "ai_models"."thinking_only" IS '是否仅允许思考模式';
COMMENT ON COLUMN "ai_models"."allow_disable_thinking" IS '是否允许用户关闭思考';
COMMENT ON COLUMN "ai_models"."default_reasoning_effort" IS '默认思考强度';
COMMENT ON COLUMN "ai_models"."supported_reasoning_efforts" IS '支持的思考强度 JSON 数组';
