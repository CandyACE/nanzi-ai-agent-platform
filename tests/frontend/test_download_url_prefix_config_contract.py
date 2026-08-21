from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure

ROOT = Path(__file__).resolve().parents[2]
MYSQL_MIG = ROOT / "db-prod/V129-add_download_url_prefix_config.sql"
PG_MIG = ROOT / "db-prod-pg/V29-add_download_url_prefix_config.sql"
SYSTEM_CONFIG_VUE = ROOT / "frontend/src/views/SystemConfig.vue"
GENERATED_FILE_SERVICE = ROOT / "app/services/ai/tools/generated_file_service.py"


def test_download_url_prefix_is_seeded_in_both_database_migrations():
    assert MYSQL_MIG.exists()
    assert PG_MIG.exists()
    mysql = MYSQL_MIG.read_text(encoding="utf-8")
    pg = PG_MIG.read_text(encoding="utf-8")

    for source in (mysql, pg):
        assert "download_url_prefix" in source
        assert "general" in source
        assert "https://your-domain.example.com" in source


def test_download_url_prefix_prefers_system_config_and_keeps_env_fallback():
    source = GENERATED_FILE_SERVICE.read_text(encoding="utf-8")

    assert 'ConfigService.get("download_url_prefix")' in source
    assert "settings.APP_PUBLIC_URL" in source


def test_system_config_shows_download_url_prefix_example():
    source = SYSTEM_CONFIG_VUE.read_text(encoding="utf-8")

    assert "download_url_prefix" in source
    assert "示例" in source
    assert "/api/v1/chat/generated-files/" in source
    assert "不要填写" in source
