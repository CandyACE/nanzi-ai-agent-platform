from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure


def test_mysql_mcp_availability_migration_is_idempotent():
    source = Path("db-prod/V109-add_mcp_tool_availability.sql").read_text()
    assert "sys_mcp_tool_cache" in source
    assert "is_available" in source
    assert "information_schema.columns" in source
    assert "DEFAULT TRUE" in source


def test_postgresql_mcp_availability_migration_is_idempotent():
    source = Path("db-prod-pg/V7-add_mcp_tool_availability.sql").read_text()
    assert 'ADD COLUMN IF NOT EXISTS "is_available"' in source
    assert 'DEFAULT TRUE' in source
    assert '远端工具是否仍存在' in source
