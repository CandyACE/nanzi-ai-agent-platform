-- V134: 增加 Agent 单次对话工具调用总次数上限配置（MySQL）
INSERT IGNORE INTO system_configs
    (`key`, `value`, `description`, `category`, `is_secret`, `created_at`, `updated_at`)
VALUES
    (
        'agent_tool_loop_global_limit',
        '50',
        '单次对话所有工具调用的总次数上限，默认 50 次，范围 1-3600，用于防止工具循环空转。',
        'agent',
        0,
        NOW(6),
        NOW(6)
    );
