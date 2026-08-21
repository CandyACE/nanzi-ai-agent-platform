-- ----------------------------------------------------------------
-- V126: Add Context Management Configuration Group
-- 将上下文管理相关配置独立为 "agent_context" 分组，并调整默认 Token 预算为 64k。
--
-- 新增配置（分组: agent_context）:
--   - agent_context_max_tokens          上下文 Token 预算上限，默认 65536 (64k)
--   - agent_context_compaction_enabled  是否启用历史溢出摘录压缩
--   - agent_context_compaction_max_chars 溢出压缩时正文截断的最大字符数
--   - agent_context_llm_summary_enabled 是否启用基于 LLM 的历史语义摘要
-- 同时将原属于 agent 分组的 agent_max_context_messages 移入 agent_context 分组，
-- 使「上下文管理」相关配置集中展示。
-- ----------------------------------------------------------------

-- 新增上下文管理配置项
INSERT IGNORE INTO `system_configs` (`key`, `value`, `description`, `category`, `is_secret`) VALUES
('agent_context_max_tokens', '65536', '发送给 LLM 的上下文 Token 预算上限 (默认 64k，超过则从最早历史开始截断)', 'agent_context', 0),
('agent_context_compaction_enabled', 'true', '是否启用历史溢出摘录压缩：上下文超预算时把早期对话压缩为摘录注入', 'agent_context', 0),
('agent_context_compaction_max_chars', '1200', '溢出压缩摘录中正文部分的最大字符数 (仅保留首末尾摘要)', 'agent_context', 0),
('agent_context_llm_summary_enabled', 'true', '是否启用基于 LLM 的历史语义摘要 (失败或超时自动降级为确定性摘录)', 'agent_context', 0);

-- 将最大历史消息条数配置移入上下文管理分组，并将默认条数提升为 60
UPDATE `system_configs`
SET `value` = '60',
    `description` = '发送给 LLM 的最大历史消息条目数（token 预算优先，此处作为绝对兜底上限，默认 60）',
    `category` = 'agent_context',
    `updated_at` = CURRENT_TIMESTAMP
WHERE `key` = 'agent_max_context_messages';