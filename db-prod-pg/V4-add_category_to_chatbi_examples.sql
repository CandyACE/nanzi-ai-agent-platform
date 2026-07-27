-- 为 ChatBI 经验案例表增加类别列 (PostgreSQL)
ALTER TABLE ai_chatbi_examples ADD COLUMN IF NOT EXISTS category VARCHAR(32) DEFAULT 'general';
