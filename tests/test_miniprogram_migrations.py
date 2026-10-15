"""小程序微端迁移文件的契约测试。

这些断言只读 SQL 文本、不连数据库——迁移由用户手工导入，
测试环境不会自动执行迁移（app/core/database.py:init_db 只做 SELECT 1 健康检查）。
"""

from pathlib import Path

import pytest

pytestmark = pytest.mark.no_infrastructure

REPO_ROOT = Path(__file__).resolve().parents[1]
MYSQL_DIR = REPO_ROOT / "db-prod"
PG_DIR = REPO_ROOT / "db-prod-pg"

MYSQL_CREATE = MYSQL_DIR / "V170-create_wechat_bindings.sql"
PG_CREATE = PG_DIR / "V71-create_wechat_bindings.sql"
MYSQL_SEED = MYSQL_DIR / "V171-seed_miniprogram_role_and_config.sql"
PG_SEED = PG_DIR / "V72-seed_miniprogram_role_and_config.sql"

TABLE = "ai_agent_wechat_bindings"


def test_migration_files_exist():
    for path in (MYSQL_CREATE, PG_CREATE, MYSQL_SEED, PG_SEED):
        assert path.exists(), f"缺少迁移文件: {path}"


def test_mysql_create_table_is_idempotent_and_has_unique_binding_key():
    sql = MYSQL_CREATE.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS" in sql
    assert TABLE in sql
    # (appid, openid) 必须唯一，否则同一微信会开出多个账号
    assert "ux_wechat_binding_appid_openid" in sql
    for column in ("user_id", "appid", "openid", "unionid", "last_login_at"):
        assert column in sql


def test_pg_create_table_is_idempotent_and_has_unique_binding_key():
    sql = PG_CREATE.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS" in sql
    assert TABLE in sql
    assert "ux_wechat_binding_appid_openid" in sql
    # PG 侧索引用 IF NOT EXISTS 保证可重复导入
    assert "CREATE INDEX IF NOT EXISTS" in sql


def test_role_seed_is_idempotent_in_both_dialects():
    mysql = MYSQL_SEED.read_text(encoding="utf-8")
    pg = PG_SEED.read_text(encoding="utf-8")

    assert "INSERT IGNORE" in mysql
    assert "ON CONFLICT" in pg


def test_role_seed_uses_stable_code_and_grants_no_permissions():
    """D3：只种空角色。种了权限行会让「可见智能体」白名单被意外放宽。"""
    for path in (MYSQL_SEED, PG_SEED):
        sql = path.read_text(encoding="utf-8")
        assert "miniprogram_user" in sql
        assert "小程序用户" in sql
        assert "ai_agent_resource_permissions" not in sql


def test_config_seed_defaults_disabled_and_never_overwrites_value():
    """开关默认关闭；且种子不得覆盖管理员已改过的 value。"""
    for path in (MYSQL_SEED, PG_SEED):
        sql = path.read_text(encoding="utf-8")
        assert "miniprogram_enabled" in sql
        assert "'false'" in sql
        # 不允许 DO UPDATE / ON DUPLICATE KEY UPDATE——那会在重复导入时
        # 覆盖管理员已开启的开关状态
        assert "ON DUPLICATE KEY UPDATE" not in sql
        assert "DO UPDATE" not in sql
