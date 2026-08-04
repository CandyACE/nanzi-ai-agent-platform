-- V112: 为已存在的技能发布版本表补充撤销审核字段
-- 该补丁针对已执行旧版技能发布表的环境，只执行一次。
ALTER TABLE skill_publication_versions
    ADD COLUMN withdrawn_by BIGINT NULL COMMENT '撤销提交的用户 ID',
    ADD COLUMN withdrawn_at DATETIME NULL COMMENT '提交撤销时间';
