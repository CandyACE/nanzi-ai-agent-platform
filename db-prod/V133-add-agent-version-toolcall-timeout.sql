-- V133: 增加 Agent 版本级工具调用超时配置（MySQL）
ALTER TABLE `ai_agent_versions`
    ADD COLUMN `toolcall_timeout_seconds` INT NULL
    COMMENT '智能体版本级工具调用超时时间（秒），NULL 表示跟随全局，范围 1-86400'
    AFTER `tools`;
