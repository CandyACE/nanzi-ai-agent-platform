from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_mysql_migration_backfills_locked_primary_capabilities_idempotently():
    migration = (
        REPO_ROOT / "db-prod" / "V131-add_agent_legacy_primary_capabilities.sql"
    )

    assert migration.exists()
    sql = migration.read_text(encoding="utf-8")

    assert "`agent_type` = 'GENERAL'" in sql
    assert "`agent_type` = 'CHATBI'" in sql
    assert "`agent_type` = 'KNOWLEDGE_BASE'" in sql
    assert "general_chat" in sql
    assert "data_query" in sql
    assert "knowledge_base" in sql
    assert "JSON_CONTAINS" in sql


def test_postgresql_migration_backfills_locked_primary_capabilities_idempotently():
    migration = (
        REPO_ROOT
        / "db-prod-pg"
        / "V31-add_agent_legacy_primary_capabilities.sql"
    )

    assert migration.exists()
    sql = migration.read_text(encoding="utf-8")

    assert '"agent_type" = \'GENERAL\'' in sql
    assert '"agent_type" = \'CHATBI\'' in sql
    assert '"agent_type" = \'KNOWLEDGE_BASE\'' in sql
    assert "general_chat" in sql
    assert "data_query" in sql
    assert "knowledge_base" in sql
    assert "@>" in sql
    assert "'[\"general_chat\"]'::jsonb" in sql
