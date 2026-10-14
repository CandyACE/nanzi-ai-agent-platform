-- 同 db-prod/V168：智能体级资源限制的作用域列与索引。
ALTER TABLE ai_agent_resource_permissions
    ADD COLUMN IF NOT EXISTS agent_id VARCHAR(36) NULL;

CREATE INDEX IF NOT EXISTS "idx_user_agent_res"
    ON ai_agent_resource_permissions (user_id, agent_id, resource_type);
CREATE INDEX IF NOT EXISTS "idx_role_agent_res"
    ON ai_agent_resource_permissions (role_id, agent_id, resource_type);
