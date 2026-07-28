-- 增加 MCP 服务 scope 作用域 (global/personal) 与 user_id 创建者隔离字段
ALTER TABLE "sys_mcp_servers" ADD COLUMN IF NOT EXISTS "scope" VARCHAR(20) NOT NULL DEFAULT 'global';
ALTER TABLE "sys_mcp_servers" ADD COLUMN IF NOT EXISTS "user_id" BIGINT NULL;

-- 移除历史全局单列 server_name 唯一约束以支持多作用域隔离
ALTER TABLE "sys_mcp_servers" DROP CONSTRAINT IF EXISTS "sys_mcp_servers_server_name_key";

COMMENT ON COLUMN "sys_mcp_servers"."scope" IS '作用域：global 平台服务，personal 个人私有服务';
COMMENT ON COLUMN "sys_mcp_servers"."user_id" IS '创建者用户 ID（仅个人私有服务生效）';

-- 注册 MCP 工具扩展 菜单权限节点
INSERT INTO "ai_agent_resource_permissions" ("resource_type", "resource_id", "enabled", "created_at", "updated_at")
SELECT 'menu', 'menu:mcp_management', TRUE, NOW(), NOW()
WHERE NOT EXISTS (
    SELECT 1
    FROM "ai_agent_resource_permissions"
    WHERE "resource_type" = 'menu'
      AND "resource_id" = 'menu:mcp_management'
);
