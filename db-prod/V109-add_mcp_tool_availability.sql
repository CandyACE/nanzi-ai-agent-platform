-- V109: 记录 MCP 工具是否仍存在于远端服务
--
-- is_published 表示平台是否允许智能体使用；
-- is_available 表示最近一次同步时远端是否仍返回该工具。
SET @column_exists := (
    SELECT COUNT(*)
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'sys_mcp_tool_cache'
      AND column_name = 'is_available'
);
SET @sql := IF(
    @column_exists = 0,
    'ALTER TABLE sys_mcp_tool_cache ADD COLUMN is_available BOOLEAN NOT NULL DEFAULT TRUE COMMENT ''远端工具是否仍存在'' AFTER is_published',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
