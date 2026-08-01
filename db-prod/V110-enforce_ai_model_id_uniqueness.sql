-- V110: model_id is the stable model selection value and must be globally unique.
-- Resolve any existing duplicate model_id values before applying this migration.

UPDATE ai_models
SET model_id = TRIM(model_id)
WHERE model_id <> TRIM(model_id);

SET @duplicate_count := (
    SELECT COUNT(*)
    FROM (
        SELECT TRIM(model_id) AS normalized_model_id
        FROM ai_models
        GROUP BY TRIM(model_id)
        HAVING COUNT(*) > 1
    ) AS duplicates
);
SET @sql := IF(
    @duplicate_count = 0,
    'SELECT 1',
    'THIS IS INVALID SQL: resolve duplicate ai_models.model_id values before V110'
);
PREPARE duplicate_check FROM @sql;
EXECUTE duplicate_check;
DEALLOCATE PREPARE duplicate_check;

SET @index_exists := (
    SELECT COUNT(*)
    FROM information_schema.statistics
    WHERE table_schema = DATABASE()
      AND table_name = 'ai_models'
      AND index_name = 'uq_ai_models_model_id'
);
SET @sql := IF(
    @index_exists = 0,
    'CREATE UNIQUE INDEX uq_ai_models_model_id ON ai_models (model_id)',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

ALTER TABLE ai_models MODIFY COLUMN api_key TEXT NULL COMMENT 'Encrypted API Key; legacy plaintext rows remain readable for migration';
