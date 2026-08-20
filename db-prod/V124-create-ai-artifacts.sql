-- V124: 通用 AI 产物元信息表。平台所有 AI 生成/导出的可下载产物
-- （Word/Excel、查询导出等）统一登记到此表，数据库只存元信息，
-- 文件内容落在对应用户的工作区目录。下载/续期/到期清理均以元信息为准。
CREATE TABLE `ai_artifacts` (
  `id` VARCHAR(32) NOT NULL COMMENT '对外 artifact_id，32 位 hex',
  `owner_user_id` BIGINT NOT NULL COMMENT '产物归属用户 ID（ai_agent_users.id）',
  `conversation_id` VARCHAR(128) DEFAULT NULL COMMENT '所属会话 ID（可为空）',
  `trace_id` VARCHAR(64) DEFAULT NULL COMMENT '所属执行 trace_id（可为空）',
  `artifact_type` VARCHAR(32) NOT NULL COMMENT '产物类型：word / excel / export',
  `filename` VARCHAR(255) NOT NULL COMMENT '下载文件名',
  `mime_type` VARCHAR(128) DEFAULT NULL COMMENT 'MIME 类型',
  `size` BIGINT NOT NULL DEFAULT 0 COMMENT '文件字节大小',
  `storage_path` VARCHAR(1024) NOT NULL COMMENT '文件实际路径（位于用户工作区内）',
  `token_hash` VARCHAR(64) NOT NULL COMMENT '下载令牌 sha256',
  `expires_at` DATETIME DEFAULT NULL COMMENT '过期时间（NULL 表示永不过期）',
  `created_at` DATETIME NOT NULL COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `idx_ai_artifacts_owner_user_id` (`owner_user_id`),
  KEY `idx_ai_artifacts_conversation_id` (`conversation_id`),
  KEY `idx_ai_artifacts_trace_id` (`trace_id`),
  KEY `idx_ai_artifacts_expires_at` (`expires_at`),
  KEY `idx_ai_artifacts_owner_created` (`owner_user_id`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='通用 AI 产物元信息表';