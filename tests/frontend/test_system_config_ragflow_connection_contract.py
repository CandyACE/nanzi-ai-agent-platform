from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure
ROOT = Path(__file__).resolve().parents[2]
SYSTEM_CONFIG = ROOT / "frontend/src/views/SystemConfig.vue"


def test_system_config_exposes_ragflow_connection_group_and_test_state():
    source = SYSTEM_CONFIG.read_text(encoding="utf-8")

    assert "ragflowConnectionTesting" in source
    assert "testRagflowMetadataConnection" in source
    assert "/api/portal/system/test-connection/ragflow_metadata" in source
    assert "RAGFlow 连接配置" in source
    assert "ragflow_api_url" in source
    assert "ragflow_api_key" in source
    assert "测试连接" in source
    assert "测试中..." in source
    assert "连接成功" in source
    assert "连接失败" in source


def test_system_config_ragflow_test_does_not_save_config_automatically():
    source = SYSTEM_CONFIG.read_text(encoding="utf-8")

    test_start = source.index("const testRagflowMetadataConnection")
    test_end = source.index("\nconst ", test_start + 1)
    test_source = source[test_start:test_end]

    assert "saveConfigs" not in test_source
    assert "use_saved_api_key" in test_source


def test_system_config_ragflow_rows_override_parent_vertical_spacing():
    source = SYSTEM_CONFIG.read_text(encoding="utf-8")

    assert "ragflow-config-group" in source
    assert "!-mt-4" in source or "!mt-0" in source
