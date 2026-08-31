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


def test_system_config_places_embed_test_below_optional_api_key():
    source = SYSTEM_CONFIG.read_text(encoding="utf-8")

    key_block = source.index("item.key === 'embed_api_key'")
    test_button = source.index('@click="testGlobalEmbed"')
    secret_branch = source.index("item.is_secret")
    assert "item.is_secret && item.key !== 'embed_api_key'" in source
    assert "item.key === 'embed_dimensions'" in source
    assert secret_branch < key_block
    assert test_button > source.index("item.key === 'embed_dimensions'")
    assert "API Key 可留空" in source
    assert source.count('@click="testGlobalEmbed"') == 1


def test_system_config_groups_embedding_mode_fields_with_context_hint():
    source = SYSTEM_CONFIG.read_text(encoding="utf-8")

    hint = "向量模式配置"

    assert hint in source
    assert "用于会话记忆向量化以及 Redis 模式下元数据向量化" in source
    assert "item.key === 'embed_model_name'" in source
    assert "item.key === 'embed_dimensions'" in source
    url_block = source.index("item.key === 'embed_api_url'")
    key_block = source.index("item.key === 'embed_api_key'")
    model_block = source.index("item.key === 'embed_model_name'")
    dimensions_block = source.index("item.key === 'embed_dimensions'")
    assert url_block < key_block < model_block < dimensions_block
    assert source.index(hint) > url_block
    assert "embed-config-group" in source
