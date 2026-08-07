-- V116: add per-model thinking mode configuration.

SET @thinking_enabled_exists := (
    SELECT COUNT(*)
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'ai_models'
      AND column_name = 'thinking_enabled'
);
SET @sql := IF(
    @thinking_enabled_exists = 0,
    'ALTER TABLE ai_models ADD COLUMN thinking_enabled TINYINT(1) NOT NULL DEFAULT 0 COMMENT ''是否启用思考模式'' AFTER max_output_tokens',
    'SELECT 1'
);
PREPARE add_thinking_enabled FROM @sql;
EXECUTE add_thinking_enabled;
DEALLOCATE PREPARE add_thinking_enabled;

SET @thinking_only_exists := (
    SELECT COUNT(*)
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'ai_models'
      AND column_name = 'thinking_only'
);
SET @sql := IF(
    @thinking_only_exists = 0,
    'ALTER TABLE ai_models ADD COLUMN thinking_only TINYINT(1) NOT NULL DEFAULT 0 COMMENT ''是否仅允许思考模式'' AFTER thinking_enabled',
    'SELECT 1'
);
PREPARE add_thinking_only FROM @sql;
EXECUTE add_thinking_only;
DEALLOCATE PREPARE add_thinking_only;

SET @allow_disable_thinking_exists := (
    SELECT COUNT(*)
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'ai_models'
      AND column_name = 'allow_disable_thinking'
);
SET @sql := IF(
    @allow_disable_thinking_exists = 0,
    'ALTER TABLE ai_models ADD COLUMN allow_disable_thinking TINYINT(1) NOT NULL DEFAULT 1 COMMENT ''是否允许用户关闭思考'' AFTER thinking_only',
    'SELECT 1'
);
PREPARE add_allow_disable_thinking FROM @sql;
EXECUTE add_allow_disable_thinking;
DEALLOCATE PREPARE add_allow_disable_thinking;

SET @default_reasoning_effort_exists := (
    SELECT COUNT(*)
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'ai_models'
      AND column_name = 'default_reasoning_effort'
);
SET @sql := IF(
    @default_reasoning_effort_exists = 0,
    'ALTER TABLE ai_models ADD COLUMN default_reasoning_effort VARCHAR(32) NOT NULL DEFAULT ''auto'' COMMENT ''默认思考强度'' AFTER allow_disable_thinking',
    'SELECT 1'
);
PREPARE add_default_reasoning_effort FROM @sql;
EXECUTE add_default_reasoning_effort;
DEALLOCATE PREPARE add_default_reasoning_effort;

SET @supported_reasoning_efforts_exists := (
    SELECT COUNT(*)
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'ai_models'
      AND column_name = 'supported_reasoning_efforts'
);
SET @sql := IF(
    @supported_reasoning_efforts_exists = 0,
    'ALTER TABLE ai_models ADD COLUMN supported_reasoning_efforts TEXT NULL COMMENT ''支持的思考强度 JSON 数组'' AFTER default_reasoning_effort',
    'SELECT 1'
);
PREPARE add_supported_reasoning_efforts FROM @sql;
EXECUTE add_supported_reasoning_efforts;
DEALLOCATE PREPARE add_supported_reasoning_efforts;

UPDATE ai_models
SET supported_reasoning_efforts = '["low","high","max"]'
WHERE supported_reasoning_efforts IS NULL OR supported_reasoning_efforts = '';
