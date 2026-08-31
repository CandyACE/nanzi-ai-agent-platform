-- Simple migration
ALTER TABLE ai_agents ADD COLUMN is_enabled BOOLEAN DEFAULT 1 NOT NULL COMMENT '是否启用' AFTER is_system;

UPDATE ai_agents
SET is_enabled = 0
WHERE name = 'metadata-specialist';
