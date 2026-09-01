from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure
SYSTEM_CONFIG = Path(__file__).resolve().parents[2] / "frontend/src/views/SystemConfig.vue"


def test_knowledge_dataset_selector_explains_its_test_and_configuration_action():
    source = SYSTEM_CONFIG.read_text(encoding="utf-8")

    assert "测试 &amp; 配置默认知识库" in source
    assert "item.key === 'knowledge_ragflow_dataset_ids'" in source
    assert "item.key === 'knowledge_ragflow_dataset_ids' ? '测试连接并配置默认知识库'" in source
