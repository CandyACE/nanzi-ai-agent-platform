-- V110: MCP 固定客户端凭证与可选签名 UserContext 配置
ALTER TABLE sys_mcp_servers
    ADD COLUMN credential_mode VARCHAR(40) NOT NULL DEFAULT 'static',
    ADD COLUMN fixed_token_encrypted TEXT NULL,
    ADD COLUMN user_assertion_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN user_assertion_header VARCHAR(100) NOT NULL DEFAULT 'X-Nanzi-User-Assertion',
    ADD COLUMN user_assertion_audience VARCHAR(255) NULL,
    ADD COLUMN user_assertion_key_id VARCHAR(100) NULL,
    ADD COLUMN user_assertion_issuer VARCHAR(255) NULL DEFAULT 'nanzi-platform',
    ADD COLUMN user_assertion_private_key_encrypted TEXT NULL;
