-- V166: 智能体版本配置新增「是否允许手动切换模型」开关。
-- 需求背景：智能体版本需要能锁定模型——关闭后，对话输入框不再展示模型切换入口，
--           用户只能使用该版本配置的编排模型。
-- 变更范围：仅新增一个非空列，DEFAULT 1，历史数据自动按「允许」处理（不做数据回填）。
-- 依赖：ai_agent_versions（V5 建表，V35 增加 synthesis_temperature）。
-- 创建时间：2026-10-13

SET @allow_model_switch_exists := (
    SELECT COUNT(*)
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'ai_agent_versions'
      AND column_name = 'allow_model_switch'
);
SET @sql := IF(
    @allow_model_switch_exists = 0,
    'ALTER TABLE ai_agent_versions ADD COLUMN allow_model_switch TINYINT(1) NOT NULL DEFAULT 1 COMMENT ''是否允许在输入框手动切换模型：1 允许（默认），0 禁止'' AFTER synthesis_temperature',
    'SELECT 1'
);
PREPARE add_allow_model_switch FROM @sql;
EXECUTE add_allow_model_switch;
DEALLOCATE PREPARE add_allow_model_switch;
