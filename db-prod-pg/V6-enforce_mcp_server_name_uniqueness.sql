-- V6: MCP 服务显示名称全局唯一
--
-- V3 为支持作用域隔离移除了历史的单列唯一约束，但 MCP 工具在平台内
-- 使用 server_name:tool_name 作为配置标识。公共服务和个人服务如果同名，
-- 运行时无法仅凭工具名称区分来源，因此这里恢复跨作用域的大小写不敏感唯一性。

-- 先规范化历史名称，并保留每组重复名称中最早创建的记录；其余记录追加
-- 可追踪的 legacy 标记和服务 ID 前缀，避免历史数据阻塞唯一索引创建。
UPDATE "sys_mcp_servers"
   SET "server_name" = BTRIM("server_name")
 WHERE "server_name" IS DISTINCT FROM BTRIM("server_name");

DO $$
DECLARE
    duplicate RECORD;
    candidate TEXT;
    suffix TEXT;
    attempt INTEGER;
BEGIN
    FOR duplicate IN
        SELECT "id", "server_name"
          FROM (
              SELECT "id",
                     "server_name",
                     ROW_NUMBER() OVER (
                         PARTITION BY LOWER(BTRIM("server_name"))
                         ORDER BY "created_at" NULLS LAST, "id"
                     ) AS row_number
                FROM "sys_mcp_servers"
          ) AS grouped_servers
         WHERE row_number > 1
         ORDER BY "id"
    LOOP
        suffix := ' (legacy-' || REPLACE(LEFT(duplicate."id", 12), '-', '') || ')';
        candidate := LEFT(
            BTRIM(duplicate."server_name"),
            100 - LENGTH(suffix)
        ) || suffix;
        attempt := 0;

        WHILE EXISTS (
            SELECT 1
              FROM "sys_mcp_servers" AS existing
             WHERE existing."id" <> duplicate."id"
               AND LOWER(BTRIM(existing."server_name")) = LOWER(candidate)
        ) LOOP
            attempt := attempt + 1;
            candidate := LEFT(
                BTRIM(duplicate."server_name"),
                100 - LENGTH(suffix) - LENGTH(' #' || attempt::TEXT)
            ) || suffix || ' #' || attempt::TEXT;
        END LOOP;

        UPDATE "sys_mcp_servers"
           SET "server_name" = candidate
         WHERE "id" = duplicate."id";
    END LOOP;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS "ux_sys_mcp_servers_server_name_normalized"
    ON "sys_mcp_servers" (LOWER(BTRIM("server_name")));
