CREATE TABLE IF NOT EXISTS skill_publications (
    id VARCHAR(36) PRIMARY KEY,
    platform_skill_id VARCHAR(128) UNIQUE,
    source_user_id BIGINT NOT NULL REFERENCES ai_agent_users(id),
    source_personal_skill_id VARCHAR(128) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    current_version INTEGER,
    status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    revoked_at TIMESTAMP,
    revoked_by BIGINT REFERENCES ai_agent_users(id)
);

CREATE INDEX IF NOT EXISTS idx_skill_publications_source
    ON skill_publications (source_user_id, source_personal_skill_id);
CREATE INDEX IF NOT EXISTS idx_skill_publications_status
    ON skill_publications (status);

COMMENT ON TABLE "skill_publications" IS '个人技能发布到平台公共技能库的发布谱系';
COMMENT ON COLUMN "skill_publications"."id" IS '发布谱系 ID，UUID';
COMMENT ON COLUMN "skill_publications"."platform_skill_id" IS '平台公共技能唯一 ID，首次审核通过时生成';
COMMENT ON COLUMN "skill_publications"."source_user_id" IS '原个人技能所属用户 ID';
COMMENT ON COLUMN "skill_publications"."source_personal_skill_id" IS '原个人技能 ID';
COMMENT ON COLUMN "skill_publications"."name" IS '平台技能名称快照';
COMMENT ON COLUMN "skill_publications"."description" IS '平台技能描述快照';
COMMENT ON COLUMN "skill_publications"."current_version" IS '当前已发布版本号';
COMMENT ON COLUMN "skill_publications"."status" IS '发布谱系状态：PENDING 待首发、PUBLISHED 已发布、UNPUBLISHED 未发布、REVOKED 已下架';
COMMENT ON COLUMN "skill_publications"."created_at" IS '发布谱系创建时间';
COMMENT ON COLUMN "skill_publications"."updated_at" IS '发布谱系更新时间';
COMMENT ON COLUMN "skill_publications"."revoked_at" IS '平台技能下架时间';
COMMENT ON COLUMN "skill_publications"."revoked_by" IS '执行下架的用户 ID';

CREATE TABLE IF NOT EXISTS skill_publication_versions (
    id VARCHAR(36) PRIMARY KEY,
    publication_id VARCHAR(36) NOT NULL REFERENCES skill_publications(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    snapshot_path VARCHAR(1024) NOT NULL,
    content_sha256 CHAR(64) NOT NULL,
    file_count INTEGER NOT NULL DEFAULT 0,
    total_size BIGINT NOT NULL DEFAULT 0,
    submitted_by BIGINT NOT NULL REFERENCES ai_agent_users(id),
    submitted_at TIMESTAMP NOT NULL,
    reviewed_by BIGINT REFERENCES ai_agent_users(id),
    reviewed_at TIMESTAMP,
    review_comment TEXT,
    published_at TIMESTAMP,
    materialized_path VARCHAR(1024),
    withdrawn_by BIGINT REFERENCES ai_agent_users(id),
    withdrawn_at TIMESTAMP,
    CONSTRAINT ux_skill_publication_version_number UNIQUE (publication_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_skill_publication_versions_status
    ON skill_publication_versions (status);
CREATE INDEX IF NOT EXISTS idx_skill_publication_versions_publication
    ON skill_publication_versions (publication_id, status);

COMMENT ON TABLE "skill_publication_versions" IS '个人技能平台发布的候选与审核版本';
COMMENT ON COLUMN "skill_publication_versions"."id" IS '发布版本 ID，UUID';
COMMENT ON COLUMN "skill_publication_versions"."publication_id" IS '所属发布谱系 ID';
COMMENT ON COLUMN "skill_publication_versions"."version_number" IS '候选或发布版本号，从 1 开始递增';
COMMENT ON COLUMN "skill_publication_versions"."status" IS '版本状态：PENDING 待审核、APPROVED 已发布、REJECTED 已驳回、WITHDRAWN 提交者已撤销、SUPERSEDED 已被新版本替代';
COMMENT ON COLUMN "skill_publication_versions"."snapshot_path" IS '受控快照目录路径';
COMMENT ON COLUMN "skill_publication_versions"."content_sha256" IS '快照内容 SHA-256 指纹';
COMMENT ON COLUMN "skill_publication_versions"."file_count" IS '快照文件数量';
COMMENT ON COLUMN "skill_publication_versions"."total_size" IS '快照总大小，单位字节';
COMMENT ON COLUMN "skill_publication_versions"."submitted_by" IS '提交审核的用户 ID';
COMMENT ON COLUMN "skill_publication_versions"."submitted_at" IS '提交审核时间';
COMMENT ON COLUMN "skill_publication_versions"."reviewed_by" IS '审核用户 ID';
COMMENT ON COLUMN "skill_publication_versions"."reviewed_at" IS '审核时间';
COMMENT ON COLUMN "skill_publication_versions"."review_comment" IS '审核意见或驳回原因';
COMMENT ON COLUMN "skill_publication_versions"."published_at" IS '平台发布生效时间';
COMMENT ON COLUMN "skill_publication_versions"."materialized_path" IS '平台技能活动目录路径';
COMMENT ON COLUMN "skill_publication_versions"."withdrawn_by" IS '撤销提交的用户 ID';
COMMENT ON COLUMN "skill_publication_versions"."withdrawn_at" IS '提交撤销时间';
