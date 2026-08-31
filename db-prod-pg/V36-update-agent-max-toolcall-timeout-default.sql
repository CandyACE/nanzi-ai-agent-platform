-- V36: 将 Agent 单次工具调用的默认超时时间从 120 秒调整为 180 秒（PostgreSQL）
UPDATE "system_configs"
SET
    "value" = '180',
    "description" = '单次 Agent 工具调用的全局超时时间（秒），默认 180 秒，范围 1-3600；版本级配置优先于全局配置。',
    "updated_at" = CURRENT_TIMESTAMP
WHERE "key" = 'agent_max_toolcall_timeout'
  AND "value" = '120';
