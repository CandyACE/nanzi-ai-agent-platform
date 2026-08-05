-- V114: MCP 服务可选备注，便于列表与级联展示时理解用途
SET @column_exists := (
    SELECT COUNT(*)
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'sys_mcp_servers'
      AND column_name = 'remark'
);
SET @sql := IF(
    @column_exists = 0,
    'ALTER TABLE sys_mcp_servers ADD COLUMN remark VARCHAR(500) NULL COMMENT ''服务备注（选填）'' AFTER server_name',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
