-- =====================================================================
-- 变更原因：小程序微端需要业务角色与功能开关（PostgreSQL 方言）
-- 设计决策 D3：只种【空角色】，不种任何权限行。
--   智能体可见性是白名单，空角色 = 看不到任何智能体，属 fail-safe 默认；
--   可见智能体与配额由管理员在后台「角色管理」中勾选。
-- 创建时间：2026-10-15
-- 注意事项：该脚本仅做生成，不得由 Agent 自动执行，由用户手动导入。
--   使用 ON CONFLICT DO NOTHING（幂等插入，不做覆盖式更新）：
--   重复导入时不得覆盖管理员已改过的 miniprogram_enabled 开关值。
-- =====================================================================

INSERT INTO "ai_agent_roles" ("code", "name", "description")
VALUES (
    'miniprogram_user',
    '小程序用户',
    '微信小程序静默登录自动开户的用户；可见智能体与配额由管理员在后台配置'
)
ON CONFLICT ("code") DO NOTHING;

INSERT INTO "system_configs" ("key", "value", "description", "category", "is_secret")
VALUES (
    'miniprogram_enabled',
    'false',
    '是否开启微信小程序微端自动开户与签票 (true/false)',
    'other',
    FALSE
)
ON CONFLICT ("key") DO NOTHING;
