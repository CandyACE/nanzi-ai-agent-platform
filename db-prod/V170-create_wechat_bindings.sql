-- V170: 微信小程序用户身份绑定表（MySQL 方言）
-- 变更原因：小程序微端需要按 openid 定位平台账号。该映射不能塞进
--           ai_agent_users.extra_data——那里没有索引，也无法保证 (appid, openid) 唯一。
-- 需求背景：微信小程序静默登录自动开户（见 docs/superpowers/specs/2026-10-15-miniprogram-embedchat-design.md）
-- 创建时间：2026-10-15
-- 注意事项：本脚本仅由 Agent 生成，不得自动执行，请由用户手工导入更新到数据库。
--           apply_sql.py 无 schema_migrations 记录表，幂等必须写在 SQL 自身。

CREATE TABLE IF NOT EXISTS ai_agent_wechat_bindings (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '主键ID',
    user_id BIGINT NOT NULL COMMENT '平台账号ID（ai_agent_users.id）',
    appid VARCHAR(64) NOT NULL COMMENT '小程序 AppID',
    openid VARCHAR(64) NOT NULL COMMENT '该 AppID 下的微信用户标识',
    unionid VARCHAR(64) NULL COMMENT '微信开放平台统一标识，可空；用于跨应用复用同一账号',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    last_login_at DATETIME NULL COMMENT '最近一次命中该绑定的时间',
    CONSTRAINT fk_wechat_binding_user
        FOREIGN KEY (user_id) REFERENCES ai_agent_users(id)
        ON DELETE CASCADE,
    UNIQUE KEY ux_wechat_binding_appid_openid (appid, openid),
    KEY ix_wechat_binding_user_id (user_id),
    KEY ix_wechat_binding_unionid (unionid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='微信小程序身份绑定表';
