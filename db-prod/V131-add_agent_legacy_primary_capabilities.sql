-- V131: 为历史智能体补齐类型对应的锁定主能力
-- 幂等执行，保留已有扩展能力；运行时也会兼容迁移尚未执行的旧行。
UPDATE `ai_agents`
SET `capabilities` = JSON_ARRAY_APPEND(COALESCE(`capabilities`, JSON_ARRAY()), '$', 'general_chat')
WHERE `agent_type` = 'GENERAL'
  AND NOT JSON_CONTAINS(COALESCE(`capabilities`, JSON_ARRAY()), JSON_QUOTE('general_chat'));

UPDATE `ai_agents`
SET `capabilities` = JSON_ARRAY_APPEND(COALESCE(`capabilities`, JSON_ARRAY()), '$', 'data_query')
WHERE `agent_type` = 'CHATBI'
  AND NOT JSON_CONTAINS(COALESCE(`capabilities`, JSON_ARRAY()), JSON_QUOTE('data_query'));

UPDATE `ai_agents`
SET `capabilities` = JSON_ARRAY_APPEND(COALESCE(`capabilities`, JSON_ARRAY()), '$', 'knowledge_base')
WHERE `agent_type` = 'KNOWLEDGE_BASE'
  AND NOT JSON_CONTAINS(COALESCE(`capabilities`, JSON_ARRAY()), JSON_QUOTE('knowledge_base'));
