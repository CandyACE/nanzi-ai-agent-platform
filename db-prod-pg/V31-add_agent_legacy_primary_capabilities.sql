-- V31: 为历史智能体补齐类型对应的锁定主能力
-- 幂等执行，保留已有扩展能力；运行时也会兼容迁移尚未执行的旧行。
UPDATE "ai_agents"
SET "capabilities" = COALESCE("capabilities", '[]'::jsonb) || '["general_chat"]'::jsonb
WHERE "agent_type" = 'GENERAL'
  AND NOT (COALESCE("capabilities", '[]'::jsonb) @> '["general_chat"]'::jsonb);

UPDATE "ai_agents"
SET "capabilities" = COALESCE("capabilities", '[]'::jsonb) || '["data_query"]'::jsonb
WHERE "agent_type" = 'CHATBI'
  AND NOT (COALESCE("capabilities", '[]'::jsonb) @> '["data_query"]'::jsonb);

UPDATE "ai_agents"
SET "capabilities" = COALESCE("capabilities", '[]'::jsonb) || '["knowledge_base"]'::jsonb
WHERE "agent_type" = 'KNOWLEDGE_BASE'
  AND NOT (COALESCE("capabilities", '[]'::jsonb) @> '["knowledge_base"]'::jsonb);
