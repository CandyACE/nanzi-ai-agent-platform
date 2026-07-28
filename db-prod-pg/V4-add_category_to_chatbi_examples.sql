-- 为 ChatBI 经验案例表增加类别列 (PostgreSQL)
ALTER TABLE ai_chatbi_examples ADD COLUMN IF NOT EXISTS category VARCHAR(32) DEFAULT 'general';
COMMENT ON COLUMN "ai_chatbi_examples"."category" IS '案例分类：general、knowledge、data_query';
