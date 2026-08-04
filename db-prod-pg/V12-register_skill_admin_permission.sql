-- V12: 注册平台技能与发布审核的独立元素权限

INSERT INTO "ai_agent_resource_permissions"
    ("resource_type", "resource_id", "enabled", "created_at", "updated_at")
SELECT 'element', 'element:skills:admin', TRUE, NOW(), NOW()
WHERE NOT EXISTS (
    SELECT 1
    FROM "ai_agent_resource_permissions"
    WHERE "resource_type" = 'element'
      AND "resource_id" = 'element:skills:admin'
);
