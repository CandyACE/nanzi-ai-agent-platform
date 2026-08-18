-- V122: 服务端浏览器 Profile 与 Session
CREATE TABLE IF NOT EXISTS `browser_profiles` (
  `id` VARCHAR(36) NOT NULL COMMENT '浏览器 Profile 唯一标识',
  `user_id` BIGINT NOT NULL COMMENT '所属用户 ID',
  `display_name` VARCHAR(120) NOT NULL COMMENT 'Profile 显示名称',
  `encrypted_storage_ref` TEXT NOT NULL COMMENT '浏览器持久化存储内部引用，不向 API 返回 Cookie',
  `status` VARCHAR(20) NOT NULL DEFAULT 'active' COMMENT 'Profile 状态：active-启用',
  `last_used_at` DATETIME NULL COMMENT '最近使用时间',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_browser_profile_user_status` (`user_id`, `status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户级服务端浏览器登录 Profile';

CREATE TABLE IF NOT EXISTS `browser_sessions` (
  `id` VARCHAR(36) NOT NULL COMMENT '浏览器会话唯一标识',
  `profile_id` VARCHAR(36) NOT NULL COMMENT '关联的浏览器 Profile ID',
  `user_id` BIGINT NOT NULL COMMENT '所属用户 ID',
  `attached_conversation_id` VARCHAR(64) NULL COMMENT '关联的对话 ID',
  `current_url` TEXT NULL COMMENT '当前页面 URL',
  `page_title` VARCHAR(500) NULL COMMENT '当前页面标题',
  `approval_mode` VARCHAR(20) NOT NULL DEFAULT 'guarded' COMMENT '浏览器动作审批模式：guarded 或 autopilot',
  `status` VARCHAR(20) NOT NULL DEFAULT 'active' COMMENT '浏览器会话状态：active-运行中',
  `viewer_token_hash` VARCHAR(128) NULL COMMENT '浏览器查看令牌哈希，不保存明文令牌',
  `last_seen_at` DATETIME NULL COMMENT '最后心跳时间',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_browser_session_user_status` (`user_id`, `status`),
  KEY `idx_browser_session_profile_status` (`profile_id`, `status`),
  KEY `idx_browser_session_conversation` (`attached_conversation_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='服务端浏览器运行会话';
