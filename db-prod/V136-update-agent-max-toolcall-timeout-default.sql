-- V136: 将 Agent 单次工具调用的默认超时时间从 120 秒调整为 180 秒（MySQL）
UPDATE `system_configs`
SET
    `value` = '180',
    `description` = '单次 Agent 工具调用的全局超时时间（秒），默认 180 秒，范围 1-3600；版本级配置优先于全局配置。',
    `updated_at` = NOW(6)
WHERE `key` = 'agent_max_toolcall_timeout'
  AND `value` = '120'
  AND `description` = '单次 Agent 工具调用的全局超时时间（秒），默认 120 秒，范围 1-3600；版本级配置优先于全局配置。'
  AND NOT EXISTS (
      SELECT 1
      FROM `system_config_history` AS history
      WHERE history.`config_key` = 'agent_max_toolcall_timeout'
        AND history.`new_value` = '120'
        AND history.`change_type` IN ('CREATE', 'UPDATE')
  );
