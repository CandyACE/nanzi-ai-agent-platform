"""Contract: system default multimodal model config is seeded and selectable."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SYSTEM_CONFIG = (ROOT / "frontend/src/views/SystemConfig.vue").read_text(encoding="utf-8")
MYSQL_MIG = ROOT / "db-prod/V120-add_default_multimodal_model_config.sql"
PG_MIG = ROOT / "db-prod-pg/V20-add_default_multimodal_model_config.sql"


def test_system_config_exposes_default_multimodal_model_dropdown():
    assert "multimodal_model_name" in SYSTEM_CONFIG
    assert "multimodalModelsForConfig" in SYSTEM_CONFIG
    assert "未配置（不支持识图时提示用户）" in SYSTEM_CONFIG
    assert "'llm_model_name',\n      'multimodal_model_name'" in SYSTEM_CONFIG or (
        "llm_model_name" in SYSTEM_CONFIG and "multimodal_model_name" in SYSTEM_CONFIG
    )


def test_default_multimodal_model_migrations_seed_agent_category():
    mysql = MYSQL_MIG.read_text(encoding="utf-8")
    pg = PG_MIG.read_text(encoding="utf-8")
    for text in (mysql, pg):
        assert "multimodal_model_name" in text
        assert "'agent'" in text or '"agent"' in text
        assert "识图" in text or "多模态" in text
