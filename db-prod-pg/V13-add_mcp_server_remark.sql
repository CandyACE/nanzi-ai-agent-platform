-- V13: MCP 服务可选备注，便于列表与级联展示时理解用途
ALTER TABLE "sys_mcp_servers"
    ADD COLUMN IF NOT EXISTS "remark" VARCHAR(500) NULL;

COMMENT ON COLUMN "sys_mcp_servers"."remark"
    IS '服务备注（选填），用于列表与级联展示';
