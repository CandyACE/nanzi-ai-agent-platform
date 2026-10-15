-- =====================================================================
-- 变更原因：小程序微端需要按 openid 定位平台账号。该映射不能塞进
--           ai_agent_users.extra_data——那里没有索引，也无法保证 (appid, openid) 唯一。
-- 需求背景：微信小程序静默登录自动开户（PostgreSQL 方言）
-- 创建时间：2026-10-15
-- 注意事项：该脚本仅做生成，不得由 Agent 自动执行，由用户手动导入更新到数据库。
--           apply_sql.py 无 schema_migrations 记录表，幂等必须写在 SQL 自身。
-- =====================================================================

CREATE TABLE IF NOT EXISTS "ai_agent_wechat_bindings" (
    "id" BIGSERIAL PRIMARY KEY,
    -- 平台账号ID（ai_agent_users.id）
    "user_id" BIGINT NOT NULL,
    -- 小程序 AppID
    "appid" VARCHAR(64) NOT NULL,
    -- 该 AppID 下的微信用户标识
    "openid" VARCHAR(64) NOT NULL,
    -- 微信开放平台统一标识，可空；用于跨应用复用同一账号
    "unionid" VARCHAR(64),
    -- 创建时间
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- 最近一次命中该绑定的时间
    "last_login_at" TIMESTAMP,
    CONSTRAINT "fk_wechat_binding_user"
        FOREIGN KEY ("user_id") REFERENCES "ai_agent_users" ("id")
        ON DELETE CASCADE,
    CONSTRAINT "ux_wechat_binding_appid_openid" UNIQUE ("appid", "openid")
);

CREATE INDEX IF NOT EXISTS "ix_wechat_binding_user_id"
    ON "ai_agent_wechat_bindings" ("user_id");

CREATE INDEX IF NOT EXISTS "ix_wechat_binding_unionid"
    ON "ai_agent_wechat_bindings" ("unionid");
