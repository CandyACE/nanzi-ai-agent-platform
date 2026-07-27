from pathlib import Path

import pytest

from app.core.config import Settings


ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.no_infrastructure


def _build_settings(**overrides):
    values = {
        "_env_file": None,
        "DATABASE_TYPE": "mysql",
        "MYSQL_HOST": "localhost",
        "MYSQL_DB": "nanzi_ai_agent_platform",
        "MYSQL_USER": "root",
        "MYSQL_PASSWORD": "secret",
        "POSTGRES_HOST": "pg.local",
        "POSTGRES_PORT": 5432,
        "POSTGRES_DB": "nanzi_ai_agent_platform",
        "POSTGRES_USER": "postgres",
        "POSTGRES_PASSWORD": "secret",
        "REDIS_HOST": "localhost",
        "ENCRYPTION_KEY": "KkJgK_d-1Jda9CAp7iGhRDzuXLYZfnid2siBeIC5lqw=",
    }
    values.update(overrides)
    return Settings(**values)


def test_database_type_defaults_to_mysql_when_not_configured():
    settings = _build_settings()

    assert settings.DATABASE_TYPE == "mysql"


def test_database_type_accepts_postgresql_override():
    settings = _build_settings(DATABASE_TYPE="postgresql")

    assert settings.DATABASE_TYPE == "postgresql"


def test_database_urls_use_database_type_specific_async_and_sync_drivers():
    mysql = _build_settings()
    assert mysql.DATABASE_ASYNC_URL.drivername == "mysql+aiomysql"
    assert mysql.DATABASE_SYNC_URL.startswith("mysql+pymysql://")

    postgresql = _build_settings(DATABASE_TYPE="postgresql")
    assert postgresql.DATABASE_ASYNC_URL.drivername == "postgresql+psycopg"
    assert postgresql.DATABASE_SYNC_URL.startswith("postgresql+psycopg://")


@pytest.mark.parametrize("database_type", ["postgres", "pg", "POSTGRESQL"])
def test_database_type_accepts_postgresql_aliases(database_type):
    settings = _build_settings(DATABASE_TYPE=database_type)

    assert settings.DATABASE_ASYNC_URL.drivername == "postgresql+psycopg"


def test_database_type_rejects_unknown_values():
    settings = _build_settings(DATABASE_TYPE="oracle")

    with pytest.raises(ValueError, match="Unsupported DATABASE_TYPE"):
        _ = settings.DATABASE_ASYNC_URL


def test_postgresql_settings_do_not_require_mysql_fields():
    values = {
        "_env_file": None,
        "DATABASE_TYPE": "postgresql",
        "POSTGRES_HOST": "localhost",
        "POSTGRES_DB": "nanzi_ai_agent_platform",
        "POSTGRES_USER": "postgres",
        "POSTGRES_PASSWORD": "secret",
        "REDIS_HOST": "localhost",
        "ENCRYPTION_KEY": "KkJgK_d-1Jda9CAp7iGhRDzuXLYZfnid2siBeIC5lqw=",
    }

    settings = Settings(**values)

    assert settings.DATABASE_ASYNC_URL.drivername == "postgresql+psycopg"


def test_mysql_url_reports_missing_selected_fields():
    settings = _build_settings(MYSQL_HOST=None, MYSQL_DB=None, MYSQL_USER=None, MYSQL_PASSWORD=None)

    with pytest.raises(ValueError, match="MySQL database configuration is incomplete"):
        _ = settings.DATABASE_ASYNC_URL


def test_environment_files_document_mysql_default_database_type():
    assert "DATABASE_TYPE=mysql" in (ROOT / "env.example").read_text(encoding="utf-8")
    dotenv_content = (ROOT / ".env").read_text(encoding="utf-8")
    assert "DATABASE_TYPE=" in dotenv_content


def test_wait_for_services_selects_the_configured_database():
    script = (ROOT / "scripts/wait-for-services.sh").read_text(encoding="utf-8")

    assert 'database_type="${DATABASE_TYPE:-mysql}"' in script
    assert 'database_host="${POSTGRES_HOST:-localhost}"' in script
    assert 'database_port="${POSTGRES_PORT:-5432}"' in script
