-- V67: 智能体版本配置新增「是否允许手动切换模型」开关（PostgreSQL 版本，对应 MySQL V166）。
-- 需求背景：智能体版本需要能锁定模型——关闭后，对话输入框不再展示模型切换入口。
-- 变更范围：仅新增一个非空列，DEFAULT TRUE，历史数据自动按「允许」处理。
-- PG 原生支持 IF NOT EXISTS，因此无需依赖错误码吞掉，真正幂等。
-- 创建时间：2026-10-13

ALTER TABLE "ai_agent_versions"
    ADD COLUMN IF NOT EXISTS "allow_model_switch" BOOLEAN NOT NULL DEFAULT TRUE;

COMMENT ON COLUMN "ai_agent_versions"."allow_model_switch" IS '是否允许在输入框手动切换模型：TRUE 允许（默认），FALSE 禁止';

-- 兜底：若历史数据因外部手段写入了 NULL，按「允许」归一，避免前端把未知值当成禁止。
UPDATE "ai_agent_versions" SET "allow_model_switch" = TRUE WHERE "allow_model_switch" IS NULL;
