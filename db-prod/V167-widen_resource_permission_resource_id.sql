-- 禁用项候选（工具名 / 公共技能 id）与 MCP 运行时名长度可达 255，而 resource_id 仍是 VARCHAR(100)。
-- schema 校验放宽到 255 后必须同步扩列，否则超长项会在写入时报错（此前表现为整页权限保存 422）。
ALTER TABLE `ai_agent_resource_permissions`
    MODIFY COLUMN `resource_id` VARCHAR(255) NOT NULL COMMENT 'External ID (UUID) or String ID of the resource';
