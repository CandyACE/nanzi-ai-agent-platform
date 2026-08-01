-- V8: model_id is the stable model selection value and must be globally unique.
-- Resolve any existing duplicate model_id values before applying this migration.

UPDATE "ai_models"
   SET "model_id" = BTRIM("model_id")
 WHERE "model_id" IS DISTINCT FROM BTRIM("model_id");

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM "ai_models"
        GROUP BY BTRIM("model_id")
        HAVING COUNT(*) > 1
    ) THEN
        RAISE EXCEPTION 'Resolve duplicate ai_models.model_id values before V8';
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS "uq_ai_models_model_id"
    ON "ai_models" ("model_id");

ALTER TABLE "ai_models"
    ALTER COLUMN "api_key" TYPE TEXT;
