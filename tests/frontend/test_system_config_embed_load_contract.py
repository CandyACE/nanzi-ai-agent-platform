from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure

ROOT = Path(__file__).resolve().parents[2]
SYSTEM_CONFIG = ROOT / "frontend/src/views/SystemConfig.vue"


def test_system_config_can_load_embed_from_model_registry():
    source = SYSTEM_CONFIG.read_text(encoding="utf-8")

    assert "loadEmbedConfigFromModel" in source
    assert "embeddingModelsForConfig" in source
    assert "加载配置" in source
    assert "从模型管理选择 Embedding" in source
    assert "selectedEmbedModelId" in source
