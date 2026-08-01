-- V111: add optional model context and output token limits.
-- NULL keeps the provider/AgentScope default behavior for existing models.

SET @context_size_exists := (
    SELECT COUNT(*)
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'ai_models'
      AND column_name = 'context_size'
);
SET @sql := IF(
    @context_size_exists = 0,
    'ALTER TABLE ai_models ADD COLUMN context_size INT NULL COMMENT ''Model context window in tokens'' AFTER api_key',
    'SELECT 1'
);
PREPARE add_context_size FROM @sql;
EXECUTE add_context_size;
DEALLOCATE PREPARE add_context_size;

SET @max_output_tokens_exists := (
    SELECT COUNT(*)
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'ai_models'
      AND column_name = 'max_output_tokens'
);
SET @sql := IF(
    @max_output_tokens_exists = 0,
    'ALTER TABLE ai_models ADD COLUMN max_output_tokens INT NULL COMMENT ''Maximum output tokens per request'' AFTER context_size',
    'SELECT 1'
);
PREPARE add_max_output_tokens FROM @sql;
EXECUTE add_max_output_tokens;
DEALLOCATE PREPARE add_max_output_tokens;
