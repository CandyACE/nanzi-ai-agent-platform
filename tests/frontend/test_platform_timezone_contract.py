"""契约：平台时区配置贯通迁移、设置页、调度、公开配置与 Docker 兜底。"""

from pathlib import Path

import pytest

pytestmark = pytest.mark.no_infrastructure

ROOT = Path(__file__).resolve().parents[2]

MYSQL_MIG = ROOT / "db-prod/V115-add_platform_timezone_config.sql"
PG_MIG = ROOT / "db-prod-pg/V14-add_platform_timezone_config.sql"
PLATFORM_TZ = (ROOT / "app/services/platform_timezone.py").read_text(encoding="utf-8")
SCHEDULER = (ROOT / "app/services/ai/scheduler_service.py").read_text(encoding="utf-8")
SYSTEM_API = (ROOT / "app/api/portal/endpoints/system.py").read_text(encoding="utf-8")
AUTH_API = (ROOT / "app/api/portal/endpoints/auth.py").read_text(encoding="utf-8")
MAIN = (ROOT / "app/main.py").read_text(encoding="utf-8")
SYSTEM_CONFIG_VUE = (ROOT / "frontend/src/views/SystemConfig.vue").read_text(encoding="utf-8")
TASK_CENTER = (ROOT / "frontend/src/views/TaskCenter.vue").read_text(encoding="utf-8")
PLATFORM_TZ_TS = (ROOT / "frontend/src/utils/platformTimezone.ts").read_text(encoding="utf-8")
DOCKERFILE = (ROOT / "docker/Dockerfile").read_text(encoding="utf-8")
COMPOSE = (ROOT / "docker/docker-compose.yml").read_text(encoding="utf-8")
COMPOSE_AI = (ROOT / "docker/docker-compose.ai-agent.yml").read_text(encoding="utf-8")
TIME_ANCHOR = (ROOT / "app/services/ai/time_anchor.py").read_text(encoding="utf-8")
SYSTEM_TOOLS = (ROOT / "app/services/ai/tools/system_tools.py").read_text(encoding="utf-8")


def test_platform_timezone_migrations_seed_general_config():
    assert MYSQL_MIG.exists()
    assert PG_MIG.exists()
    mysql = MYSQL_MIG.read_text(encoding="utf-8")
    pg = PG_MIG.read_text(encoding="utf-8")
    assert "platform_timezone" in mysql
    assert "Asia/Shanghai" in mysql
    assert "general" in mysql
    assert "platform_timezone" in pg
    assert "Asia/Shanghai" in pg


def test_platform_timezone_service_defaults_and_key():
    assert 'PLATFORM_TIMEZONE_CONFIG_KEY = "platform_timezone"' in PLATFORM_TZ
    assert 'DEFAULT_PLATFORM_TIMEZONE = "Asia/Shanghai"' in PLATFORM_TZ
    assert "def platform_now" in PLATFORM_TZ
    assert "async def refresh_platform_timezone" in PLATFORM_TZ


def test_scheduler_uses_platform_timezone_explicitly():
    assert "get_cached_platform_timezone" in SCHEDULER
    assert "CronTrigger.from_crontab(" in SCHEDULER
    assert "timezone=get_cached_platform_timezone()" in SCHEDULER
    assert "apply_platform_timezone_change" in SCHEDULER
    assert "timezone('Asia/Shanghai')" not in SCHEDULER
    assert 'timezone("Asia/Shanghai")' not in SCHEDULER


def test_config_update_reloads_scheduler_and_startup_refreshes():
    assert "platform_timezone" in SYSTEM_API
    assert "apply_platform_timezone_change" in SYSTEM_API
    assert "refresh_platform_timezone" in MAIN


def test_public_config_exposes_platform_timezone():
    assert "platform_timezone" in AUTH_API
    assert "get_platform_timezone" in AUTH_API


def test_system_config_ui_has_timezone_select():
    assert "platform_timezone" in SYSTEM_CONFIG_VUE
    assert "Asia/Shanghai（中国标准时间，推荐）" in SYSTEM_CONFIG_VUE
    assert "'general'" in SYSTEM_CONFIG_VUE
    assert "orderedCategories" in SYSTEM_CONFIG_VUE


def test_frontend_task_center_formats_with_platform_timezone():
    assert "formatInPlatformTimezoneCompact" in TASK_CENTER
    assert "setPlatformTimezone" in PLATFORM_TZ_TS
    assert "formatInPlatformTimezone" in PLATFORM_TZ_TS


def test_docker_defaults_to_asia_shanghai():
    assert "ENV TZ=Asia/Shanghai" in DOCKERFILE
    assert "tzdata" in DOCKERFILE
    assert "TZ=${TZ:-Asia/Shanghai}" in COMPOSE
    assert "PLATFORM_TIMEZONE=${PLATFORM_TIMEZONE:-Asia/Shanghai}" in COMPOSE
    assert "TZ=${TZ:-Asia/Shanghai}" in COMPOSE_AI


def test_time_anchor_and_tools_prefer_platform_timezone():
    assert "get_cached_platform_timezone" in TIME_ANCHOR
    assert 'return "Asia/Shanghai"' in TIME_ANCHOR
    assert "get_cached_platform_timezone" in SYSTEM_TOOLS
