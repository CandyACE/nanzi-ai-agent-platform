from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure
SYSTEM_CONFIG = Path(__file__).resolve().parents[2] / "frontend/src/views/SystemConfig.vue"


def test_local_data_api_keeps_common_timeout_items_visible():
    source = SYSTEM_CONFIG.read_text(encoding="utf-8")

    assert "commonDataApiKeys" in source
    assert "data_api_timeout_seconds" in source
    assert "schema_api_timeout_seconds" in source
    assert "[modeItem, ...restItems.filter" in source


def test_remote_data_api_has_grouped_config_and_connection_test():
    source = SYSTEM_CONFIG.read_text(encoding="utf-8")

    assert "remote-sql-config-group" in source
    assert "远程 SQL 执行配置" in source
    assert "use_saved_external_sql_api_key" in source
    assert "仅测试连接，不会自动保存配置" in source
