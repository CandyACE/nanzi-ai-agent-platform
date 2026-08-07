-- V16: align model thinking configuration with AgentScope native parameters.
-- Supported values: none, minimal, low, medium, high, xhigh.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ai_models' AND column_name = 'thinking_enabled'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ai_models' AND column_name = 'thinking_enable'
    ) THEN
        ALTER TABLE "ai_models" RENAME COLUMN "thinking_enabled" TO "thinking_enable";
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ai_models' AND column_name = 'default_reasoning_effort'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ai_models' AND column_name = 'reasoning_effort'
    ) THEN
        ALTER TABLE "ai_models" RENAME COLUMN "default_reasoning_effort" TO "reasoning_effort";
    END IF;
END $$;

ALTER TABLE "ai_models"
    ALTER COLUMN "reasoning_effort" DROP NOT NULL,
    ALTER COLUMN "reasoning_effort" DROP DEFAULT;

UPDATE "ai_models"
SET "reasoning_effort" = NULL
WHERE "reasoning_effort" = 'auto';

UPDATE "ai_models"
SET "reasoning_effort" = 'xhigh'
WHERE "reasoning_effort" = 'max';

UPDATE "ai_models"
SET "supported_reasoning_efforts" = REPLACE("supported_reasoning_efforts", '"max"', '"xhigh"')
WHERE "supported_reasoning_efforts" LIKE '%"max"%';
