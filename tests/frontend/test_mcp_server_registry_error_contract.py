from pathlib import Path

import pytest

pytestmark = pytest.mark.no_infrastructure


SOURCE = Path("frontend/src/components/system/McpServerRegistry.vue").read_text()


def test_mcp_registry_prefers_backend_message_over_empty_detail():
    assert "const getApiErrorMessage =" in SOURCE
    assert "responseData?.message" in SOURCE
    assert "responseData?.detail" in SOURCE


def test_mcp_registry_uses_detailed_error_for_verify_and_save():
    assert "getApiErrorMessage(e, '连接失败，请检查地址或认证信息')" in SOURCE
    assert "getApiErrorMessage(e, '操作失败')" in SOURCE
