-- V7: 记录 MCP 工具是否仍存在于远端服务
--
-- is_published 表示平台是否允许智能体使用；
-- is_available 表示最近一次同步时远端是否仍返回该工具。
ALTER TABLE "sys_mcp_tool_cache"
    ADD COLUMN IF NOT EXISTS "is_available" BOOLEAN NOT NULL DEFAULT TRUE;

COMMENT ON COLUMN "sys_mcp_tool_cache"."is_available"
    IS '远端工具是否仍存在：TRUE 正常，FALSE 远端已删除';
