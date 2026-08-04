-- V11: 为已存在的技能发布版本表补充撤销审核字段

ALTER TABLE "skill_publication_versions"
    ADD COLUMN IF NOT EXISTS "withdrawn_by" BIGINT NULL;

ALTER TABLE "skill_publication_versions"
    ADD COLUMN IF NOT EXISTS "withdrawn_at" TIMESTAMP NULL;

COMMENT ON COLUMN "skill_publication_versions"."withdrawn_by"
    IS '撤销提交的用户 ID';
COMMENT ON COLUMN "skill_publication_versions"."withdrawn_at"
    IS '提交撤销时间';
