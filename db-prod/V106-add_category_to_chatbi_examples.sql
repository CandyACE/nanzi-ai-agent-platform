-- 为 ChatBI 经验案例表增加类别列
ALTER TABLE ai_chatbi_examples ADD COLUMN category VARCHAR(32) DEFAULT 'general' COMMENT '案例分类: general, knowledge, data_query';
