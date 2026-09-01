from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure
SYSTEM_CONFIG = Path(__file__).resolve().parents[2] / "frontend/src/views/SystemConfig.vue"


def test_remote_sql_guidance_links_to_open_source_install_and_api_docs():
    source = SYSTEM_CONFIG.read_text(encoding="utf-8")

    assert "远程 SQL 模式怎么使用？" in source
    assert "nanzi-api-data-platform" in source
    assert "查看部署教程" in source
    assert "查看 API 接入说明" in source
    assert "api/v1/chatbi/sql/execute" in source


def test_remote_sql_guidance_is_conditional_and_explains_configuration_order():
    source = SYSTEM_CONFIG.read_text(encoding="utf-8")

    assert "sqlExecutionMode === 'remote'" in source
    assert "部署 NanZi" in source
    assert "配置数据源" in source
    assert "创建或获取 API Key" in source
    assert "点击「测试连接」" in source


def test_sql_execution_mode_help_describes_only_local_and_remote():
    source = SYSTEM_CONFIG.read_text(encoding="utf-8")

    assert "当前支持两种执行模式" in source
    assert "local（适用于同一平台可直连数据库）" in source
    assert "remote（推荐用于独立部署）" in source
    assert "remote（调用远程数据服务）" in source
    assert "local（平台直连数据源）" in source
