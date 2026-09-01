from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure

ROOT = Path(__file__).resolve().parents[1]


def test_mysql_migration_seeds_agent_tool_timeout_config():
    source = (ROOT / "db-prod/V132-add-agent-max-toolcall-timeout.sql").read_text(encoding="utf-8")

    assert "agent_max_toolcall_timeout" in source
    assert "'120'" in source
    assert "'agent'" in source
    assert "INSERT IGNORE" in source.upper()


def test_mysql_default_timeout_upgrade_migration_preserves_custom_values():
    source = (ROOT / "db-prod/V136-update-agent-max-toolcall-timeout-default.sql").read_text(encoding="utf-8")

    assert "agent_max_toolcall_timeout" in source
    assert "'120'" in source
    assert "'180'" in source
    assert "WHERE" in source.upper()
    assert "description" in source
    assert "system_config_history" in source
    assert "new_value" in source
    assert "NOT EXISTS" in source.upper()


def test_postgres_migration_seeds_agent_tool_timeout_config_idempotently():
    source = (ROOT / "db-prod-pg/V32-add-agent-max-toolcall-timeout.sql").read_text(encoding="utf-8")

    assert "agent_max_toolcall_timeout" in source
    assert "'120'" in source
    assert "'agent'" in source
    assert "ON CONFLICT" in source.upper()


def test_postgres_default_timeout_upgrade_migration_preserves_custom_values():
    source = (ROOT / "db-prod-pg/V36-update-agent-max-toolcall-timeout-default.sql").read_text(encoding="utf-8")

    assert "agent_max_toolcall_timeout" in source
    assert "'120'" in source
    assert "'180'" in source
    assert "WHERE" in source.upper()
    assert "description" in source
    assert "system_config_history" in source
    assert "new_value" in source
    assert "NOT EXISTS" in source.upper()
