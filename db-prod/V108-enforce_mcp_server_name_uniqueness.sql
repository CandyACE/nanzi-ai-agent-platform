-- V108: MCP 服务显示名称全局唯一
--
-- V105 为支持公共/个人作用域移除了 server_name 唯一索引，但 MCP 工具在平台内
-- 使用 server_name:tool_name 作为配置标识。这里恢复跨作用域的大小写不敏感唯一性。
-- 历史重复名称保留 id 最小的一条，其余记录追加可追踪的 legacy 标记。

UPDATE sys_mcp_servers AS current_server
JOIN (
    SELECT LOWER(TRIM(server_name)) AS normalized_name, MIN(id) AS keep_id
    FROM sys_mcp_servers
    GROUP BY LOWER(TRIM(server_name))
    HAVING COUNT(*) > 1
) AS duplicates
  ON LOWER(TRIM(current_server.server_name)) = duplicates.normalized_name
 AND current_server.id <> duplicates.keep_id
SET current_server.server_name = CONCAT(
    LEFT(TRIM(current_server.server_name), 76),
    ' (legacy-',
    LEFT(REPLACE(current_server.id, '-', ''), 12),
    ')'
);

UPDATE sys_mcp_servers
SET server_name = TRIM(server_name)
WHERE server_name <> TRIM(server_name);

SET @column_exists := (
    SELECT COUNT(*)
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'sys_mcp_servers'
      AND column_name = 'server_name_normalized'
);
SET @sql := IF(
    @column_exists = 0,
    'ALTER TABLE sys_mcp_servers ADD COLUMN server_name_normalized VARCHAR(100) GENERATED ALWAYS AS (LOWER(TRIM(server_name))) STORED',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @index_exists := (
    SELECT COUNT(*)
    FROM information_schema.statistics
    WHERE table_schema = DATABASE()
      AND table_name = 'sys_mcp_servers'
      AND index_name = 'ux_sys_mcp_servers_server_name_normalized'
);
SET @sql := IF(
    @index_exists = 0,
    'CREATE UNIQUE INDEX ux_sys_mcp_servers_server_name_normalized ON sys_mcp_servers (server_name_normalized)',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
