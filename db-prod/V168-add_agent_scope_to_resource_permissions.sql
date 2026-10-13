-- 智能体级资源限制：在「用户/角色」维度之外，再支持「× 某个智能体」的作用域。
-- agent_id IS NULL 表示现有全局禁用（存量数据一行不改），非空表示只在该智能体内生效。
-- resource_type 仍只用 forbidden_tool / forbidden_skill，判定沿用"行存在即禁用"。
ALTER TABLE `ai_agent_resource_permissions`
    ADD COLUMN `agent_id` VARCHAR(36) NULL COMMENT '智能体级限制的作用域；NULL=全局禁用' AFTER `role_id`;

-- 判定热路径按 (主体, 作用域, 类型) 取行，与既有的 user/role 索引并存。
CREATE INDEX `idx_user_agent_res` ON `ai_agent_resource_permissions` (`user_id`, `agent_id`, `resource_type`);
CREATE INDEX `idx_role_agent_res` ON `ai_agent_resource_permissions` (`role_id`, `agent_id`, `resource_type`);
