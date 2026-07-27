-- 新增 sql_execution_mode 配置项，默认值为 local
INSERT IGNORE INTO `system_configs` (`key`, `value`, `description`, `category`, `is_secret`) VALUES
('sql_execution_mode', 'local', 'SQL 执行模式 (remote: 走远程执行服务, local: 本地数据源直连执行, auto/空: 查表动态判断)', 'data_api', 0);
