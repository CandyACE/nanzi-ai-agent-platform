from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure


ROOT = Path(__file__).resolve().parents[1]


def test_mysql_browser_migration_declares_profiles_and_sessions():
    sql = (ROOT / "db-prod/V122-browser-session.sql").read_text(encoding="utf-8")
    assert "browser_profiles" in sql
    assert "browser_sessions" in sql
    assert "encrypted_storage_ref" in sql
    assert "approval_mode" in sql
    assert "COMMENT='用户级服务端浏览器登录 Profile'" in sql
    assert "COMMENT '浏览器持久化存储内部引用，不向 API 返回 Cookie'" in sql
    assert "COMMENT '浏览器动作审批模式：guarded 或 autopilot'" in sql
    assert "COMMENT '创建时间'" in sql


def test_postgresql_browser_migration_declares_same_contract():
    sql = (ROOT / "db-prod-pg/V22-browser-session.sql").read_text(encoding="utf-8")
    assert "browser_profiles" in sql
    assert "browser_sessions" in sql
    assert "user_id" in sql
    assert "profile_id" in sql
    assert "COMMENT ON TABLE \"browser_profiles\" IS '用户级服务端浏览器登录 Profile'" in sql
    assert "COMMENT ON COLUMN \"browser_profiles\".\"encrypted_storage_ref\" IS '浏览器持久化存储内部引用，不向 API 返回 Cookie'" in sql
    assert "COMMENT ON COLUMN \"browser_sessions\".\"approval_mode\" IS '浏览器动作审批模式：guarded 或 autopilot'" in sql
    assert "COMMENT ON COLUMN \"browser_sessions\".\"updated_at\" IS '最后更新时间'" in sql
