-- V113: 注册平台技能与发布审核的独立元素权限

INSERT IGNORE INTO ai_agent_resource_permissions
    (resource_type, resource_id, enabled, created_at, updated_at)
VALUES
    ('element', 'element:skills:admin', 1, NOW(), NOW());
