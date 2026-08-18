-- V22: 服务端浏览器 Profile 与 Session
CREATE TABLE IF NOT EXISTS "browser_profiles" (
    "id" VARCHAR(36) PRIMARY KEY,
    "user_id" BIGINT NOT NULL,
    "display_name" VARCHAR(120) NOT NULL,
    "encrypted_storage_ref" TEXT NOT NULL,
    "status" VARCHAR(20) NOT NULL DEFAULT 'active',
    "last_used_at" TIMESTAMP NULL,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS "idx_browser_profile_user_status"
    ON "browser_profiles" ("user_id", "status");

CREATE TABLE IF NOT EXISTS "browser_sessions" (
    "id" VARCHAR(36) PRIMARY KEY,
    "profile_id" VARCHAR(36) NOT NULL,
    "user_id" BIGINT NOT NULL,
    "attached_conversation_id" VARCHAR(64) NULL,
    "current_url" TEXT NULL,
    "page_title" VARCHAR(500) NULL,
    "approval_mode" VARCHAR(20) NOT NULL DEFAULT 'guarded',
    "status" VARCHAR(20) NOT NULL DEFAULT 'active',
    "viewer_token_hash" VARCHAR(128) NULL,
    "last_seen_at" TIMESTAMP NULL,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS "idx_browser_session_user_status"
    ON "browser_sessions" ("user_id", "status");
CREATE INDEX IF NOT EXISTS "idx_browser_session_profile_status"
    ON "browser_sessions" ("profile_id", "status");
CREATE INDEX IF NOT EXISTS "idx_browser_session_conversation"
    ON "browser_sessions" ("attached_conversation_id");

COMMENT ON TABLE "browser_profiles" IS '用户级服务端浏览器登录 Profile';
COMMENT ON COLUMN "browser_profiles"."id" IS '浏览器 Profile 唯一标识';
COMMENT ON COLUMN "browser_profiles"."user_id" IS '所属用户 ID';
COMMENT ON COLUMN "browser_profiles"."display_name" IS 'Profile 显示名称';
COMMENT ON COLUMN "browser_profiles"."encrypted_storage_ref" IS '浏览器持久化存储内部引用，不向 API 返回 Cookie';
COMMENT ON COLUMN "browser_profiles"."status" IS 'Profile 状态：active-启用';
COMMENT ON COLUMN "browser_profiles"."last_used_at" IS '最近使用时间';
COMMENT ON COLUMN "browser_profiles"."created_at" IS '创建时间';
COMMENT ON COLUMN "browser_profiles"."updated_at" IS '最后更新时间';

COMMENT ON TABLE "browser_sessions" IS '服务端浏览器运行会话';
COMMENT ON COLUMN "browser_sessions"."id" IS '浏览器会话唯一标识';
COMMENT ON COLUMN "browser_sessions"."profile_id" IS '关联的浏览器 Profile ID';
COMMENT ON COLUMN "browser_sessions"."user_id" IS '所属用户 ID';
COMMENT ON COLUMN "browser_sessions"."attached_conversation_id" IS '关联的对话 ID';
COMMENT ON COLUMN "browser_sessions"."current_url" IS '当前页面 URL';
COMMENT ON COLUMN "browser_sessions"."page_title" IS '当前页面标题';
COMMENT ON COLUMN "browser_sessions"."approval_mode" IS '浏览器动作审批模式：guarded 或 autopilot';
COMMENT ON COLUMN "browser_sessions"."status" IS '浏览器会话状态：active-运行中';
COMMENT ON COLUMN "browser_sessions"."viewer_token_hash" IS '浏览器查看令牌哈希，不保存明文令牌';
COMMENT ON COLUMN "browser_sessions"."last_seen_at" IS '最后心跳时间';
COMMENT ON COLUMN "browser_sessions"."created_at" IS '创建时间';
COMMENT ON COLUMN "browser_sessions"."updated_at" IS '最后更新时间';
