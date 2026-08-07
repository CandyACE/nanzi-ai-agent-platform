-- V117: align model thinking configuration with AgentScope native parameters.
-- Supported values: none, minimal, low, medium, high, xhigh.

SET @thinking_enable_exists := (
    SELECT COUNT(*)
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'ai_models'
      AND column_name = 'thinking_enable'
);
SET @thinking_enabled_exists := (
    SELECT COUNT(*)
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'ai_models'
      AND column_name = 'thinking_enabled'
);
SET @sql = IF(
    @thinking_enable_exists = 0 AND @thinking_enabled_exists = 1,
    'ALTER TABLE ai_models CHANGE COLUMN thinking_enabled thinking_enable TINYINT(1) NOT NULL DEFAULT 0 COMMENT ''是否启用思考模式'' AFTER max_output_tokens',
    'SELECT 1'
);
PREPARE rename_thinking_enable FROM @sql;
EXECUTE rename_thinking_enable;
DEALLOCATE PREPARE rename_thinking_enable;

SET @reasoning_effort_exists := (
    SELECT COUNT(*)
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'ai_models'
      AND column_name = 'reasoning_effort'
);
SET @default_reasoning_effort_exists := (
    SELECT COUNT(*)
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'ai_models'
      AND column_name = 'default_reasoning_effort'
);
SET @sql = IF(
    @reasoning_effort_exists = 0 AND @default_reasoning_effort_exists = 1,
    'ALTER TABLE ai_models CHANGE COLUMN default_reasoning_effort reasoning_effort VARCHAR(32) NULL DEFAULT NULL COMMENT ''AgentScope reasoning_effort；NULL 表示自动'' AFTER allow_disable_thinking',
    'SELECT 1'
);
PREPARE rename_reasoning_effort FROM @sql;
EXECUTE rename_reasoning_effort;
DEALLOCATE PREPARE rename_reasoning_effort;

UPDATE ai_models
SET reasoning_effort = NULL
WHERE reasoning_effort = 'auto';

UPDATE ai_models
SET reasoning_effort = 'xhigh'
WHERE reasoning_effort = 'max';

UPDATE ai_models
SET supported_reasoning_efforts = REPLACE(supported_reasoning_efforts, '"max"', '"xhigh"')
WHERE supported_reasoning_efforts LIKE '%"max"%';
