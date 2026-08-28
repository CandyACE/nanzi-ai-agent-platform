-- V132: 增加 Agent 单次工具调用的统一超时上限（MySQL）
INSERT IGNORE INTO system_configs
    (`key`, `value`, `description`, `category`, `is_secret`, `created_at`, `updated_at`)
VALUES
    (
        'agent_max_toolcall_timeout',
        '120',
        '单次 Agent 工具调用的全局超时时间（秒），默认 120 秒，范围 1-3600；版本级配置优先于全局配置。',
        'agent',
        0,
        NOW(6),
        NOW(6)
    );
