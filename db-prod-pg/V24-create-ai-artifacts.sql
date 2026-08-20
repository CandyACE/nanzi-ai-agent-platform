-- V24: 通用 AI 产物元信息表（PostgreSQL）。平台所有 AI 生成/导出的
-- 可下载产物（Word/Excel、查询导出等）统一登记到此表，数据库只存元信息，
-- 文件内容落在对应用户的工作区目录。下载/续期/到期清理均以元信息为准。
-- 与 MySQL 侧 db-prod/V124-create-ai-artifacts.sql 保持同一结构。
CREATE TABLE IF NOT EXISTS "ai_artifacts" (
    "id" VARCHAR(32) PRIMARY KEY,
    "owner_user_id" BIGINT NOT NULL,
    "conversation_id" VARCHAR(128) NULL,
    "trace_id" VARCHAR(64) NULL,
    "artifact_type" VARCHAR(32) NOT NULL,
    "filename" VARCHAR(255) NOT NULL,
    "mime_type" VARCHAR(128) NULL,
    "size" BIGINT NOT NULL DEFAULT 0,
    "storage_path" VARCHAR(1024) NOT NULL,
    "token_hash" VARCHAR(64) NOT NULL,
    "expires_at" TIMESTAMP NULL,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE "ai_artifacts" IS '通用 AI 产物元信息表';
COMMENT ON COLUMN "ai_artifacts"."id" IS '对外 artifact_id，32 位 hex';
COMMENT ON COLUMN "ai_artifacts"."owner_user_id" IS '产物归属用户 ID（ai_agent_users.id）';
COMMENT ON COLUMN "ai_artifacts"."conversation_id" IS '所属会话 ID（可为空）';
COMMENT ON COLUMN "ai_artifacts"."trace_id" IS '所属执行 trace_id（可为空）';
COMMENT ON COLUMN "ai_artifacts"."artifact_type" IS '产物类型：word / excel / export';
COMMENT ON COLUMN "ai_artifacts"."filename" IS '下载文件名';
COMMENT ON COLUMN "ai_artifacts"."mime_type" IS 'MIME 类型';
COMMENT ON COLUMN "ai_artifacts"."size" IS '文件字节大小';
COMMENT ON COLUMN "ai_artifacts"."storage_path" IS '文件实际路径（位于用户工作区内）';
COMMENT ON COLUMN "ai_artifacts"."token_hash" IS '下载令牌 sha256';
COMMENT ON COLUMN "ai_artifacts"."expires_at" IS '过期时间（NULL 表示永不过期）';
COMMENT ON COLUMN "ai_artifacts"."created_at" IS '创建时间';

CREATE INDEX IF NOT EXISTS "idx_ai_artifacts_owner_user_id"
    ON "ai_artifacts" ("owner_user_id");
CREATE INDEX IF NOT EXISTS "idx_ai_artifacts_conversation_id"
    ON "ai_artifacts" ("conversation_id");
CREATE INDEX IF NOT EXISTS "idx_ai_artifacts_trace_id"
    ON "ai_artifacts" ("trace_id");
CREATE INDEX IF NOT EXISTS "idx_ai_artifacts_expires_at"
    ON "ai_artifacts" ("expires_at");
CREATE INDEX IF NOT EXISTS "idx_ai_artifacts_owner_created"
    ON "ai_artifacts" ("owner_user_id", "created_at");