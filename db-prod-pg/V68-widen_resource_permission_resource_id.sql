-- 同 db-prod/V167：禁用项候选名长度可达 255，resource_id 需同步扩列。
ALTER TABLE ai_agent_resource_permissions
    ALTER COLUMN resource_id TYPE VARCHAR(255);
