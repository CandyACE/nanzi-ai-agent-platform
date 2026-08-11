-- V19: AgentScope 运行时状态注入开关（时间 / 任务态 / 上下文长度）
INSERT INTO "system_configs" ("key", "value", "description", "category", "is_secret")
VALUES
(
  'agentscope_inject_runtime_state',
  'true',
  '是否向 Agent 上下文注入 AgentScope 运行时状态（当前时间、任务态、上下文占用等）。时区跟随 platform_timezone。关闭后仅影响注入 hint，不改工具链与 HITL。',
  'general',
  false
),
(
  'agentscope_inject_time_interval_hours',
  '0.5',
  '运行时时间注入的最小间隔（小时）。距上次注入不足该间隔时不重复注入时间字段。仅在 agentscope_inject_runtime_state=true 时生效。',
  'general',
  false
)
ON CONFLICT ("key") DO UPDATE
SET
  "description" = EXCLUDED."description",
  "category" = EXCLUDED."category",
  "is_secret" = EXCLUDED."is_secret",
  "updated_at" = CURRENT_TIMESTAMP;
