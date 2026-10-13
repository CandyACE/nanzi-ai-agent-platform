"""智能体版本「是否允许手动切换模型」迁移契约测试。

历史数据必须默认「允许」：MySQL 依赖 DEFAULT 1 填充既有行，PG 依赖 DEFAULT TRUE。
"""

from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure

ROOT = Path(__file__).resolve().parents[1]


def test_mysql_migration_adds_allow_model_switch_defaulting_to_on():
    source = (ROOT / "db-prod/V166-add_allow_model_switch_to_agent_versions.sql").read_text(encoding="utf-8")

    assert "ai_agent_versions" in source
    assert "allow_model_switch TINYINT(1) NOT NULL DEFAULT 1" in source
    assert "allow_model_switch_exists" in source  # 可重复执行
    assert "1 允许（默认），0 禁止" in source


def test_postgres_migration_adds_allow_model_switch_defaulting_to_on():
    source = (ROOT / "db-prod-pg/V67-add_allow_model_switch_to_agent_versions.sql").read_text(encoding="utf-8")

    assert 'ALTER TABLE "ai_agent_versions"' in source
    assert 'ADD COLUMN IF NOT EXISTS "allow_model_switch" BOOLEAN NOT NULL DEFAULT TRUE' in source
    assert "UPDATE" in source and "IS NULL" in source  # 兜底归一为「允许」
