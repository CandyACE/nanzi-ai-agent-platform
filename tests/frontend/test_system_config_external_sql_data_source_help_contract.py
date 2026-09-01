from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure
SYSTEM_CONFIG = Path(__file__).resolve().parents[2] / "frontend/src/views/SystemConfig.vue"


def test_external_sql_data_source_help_distinguishes_default_and_ai_value():
    source = SYSTEM_CONFIG.read_text(encoding="utf-8")

    assert "external_sql_data_source" in source
    assert "默认数据源 ID" in source
    assert "AI 调用工具时传入" in source
    assert "优先使用 AI 传入的 data_source" in source
