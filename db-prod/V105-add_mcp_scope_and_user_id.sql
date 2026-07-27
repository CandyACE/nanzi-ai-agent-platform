-- 增加 MCP 服务 scope 作用域 (global/personal) 与 user_id 创建者隔离字段 (MySQL 兼容语法)
ALTER TABLE sys_mcp_servers ADD COLUMN scope VARCHAR(20) NOT NULL DEFAULT 'global';
ALTER TABLE sys_mcp_servers ADD COLUMN user_id INT NULL;

-- 移除历史全局单列 server_name 唯一索引以支持多作用域隔离
SET @exist := (SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name = 'sys_mcp_servers' AND index_name = 'server_name');
SET @sql := IF(@exist > 0, 'ALTER TABLE sys_mcp_servers DROP INDEX server_name', 'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 注册 MCP 工具扩展 菜单权限节点
INSERT IGNORE INTO ai_agent_resource_permissions (resource_type, resource_id, enabled, created_at, updated_at) VALUES
('menu', 'menu:mcp_management', 1, NOW(), NOW());
