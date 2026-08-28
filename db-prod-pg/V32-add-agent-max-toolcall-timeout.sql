-- V32: 增加 Agent 单次工具调用的统一超时上限（PostgreSQL）
INSERT INTO "system_configs"
    ("key", "value", "description", "category", "is_secret")
VALUES
    (
        'agent_max_toolcall_timeout',
        '120',
        '单次 Agent 工具调用的全局超时时间（秒），默认 120 秒，范围 1-3600；版本级配置优先于全局配置。',
        'agent',
        FALSE
    )
ON CONFLICT ("key") DO UPDATE
SET
    "description" = EXCLUDED."description",
    "category" = EXCLUDED."category",
    "is_secret" = EXCLUDED."is_secret",
    "updated_at" = CURRENT_TIMESTAMP;
