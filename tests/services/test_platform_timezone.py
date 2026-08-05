"""平台时区服务单元测试。"""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
import pytz

from app.services.platform_timezone import (
    DEFAULT_PLATFORM_TIMEZONE,
    PLATFORM_TIMEZONE_CONFIG_KEY,
    clear_platform_timezone_cache,
    format_platform_datetime,
    get_cached_platform_timezone,
    get_platform_timezone,
    platform_now,
    set_cached_platform_timezone,
    validate_timezone_name,
)

pytestmark = pytest.mark.no_infrastructure


@pytest.fixture(autouse=True)
def _reset_tz_cache(monkeypatch):
    clear_platform_timezone_cache()
    monkeypatch.delenv("TZ", raising=False)
    monkeypatch.delenv("PLATFORM_TIMEZONE", raising=False)
    yield
    clear_platform_timezone_cache()


def test_validate_timezone_name_accepts_iana():
    assert validate_timezone_name("Asia/Shanghai") == "Asia/Shanghai"
    assert validate_timezone_name(" UTC ") == "UTC"


def test_validate_timezone_name_falls_back_on_invalid():
    assert validate_timezone_name("Not/AZone") == DEFAULT_PLATFORM_TIMEZONE
    assert validate_timezone_name("") == DEFAULT_PLATFORM_TIMEZONE
    assert validate_timezone_name(None) == DEFAULT_PLATFORM_TIMEZONE


def test_cached_timezone_prefers_memory_then_env(monkeypatch):
    clear_platform_timezone_cache()
    monkeypatch.setenv("PLATFORM_TIMEZONE", "UTC")
    assert get_cached_platform_timezone() == "UTC"

    set_cached_platform_timezone("Asia/Tokyo")
    assert get_cached_platform_timezone() == "Asia/Tokyo"


def test_platform_now_is_timezone_aware():
    set_cached_platform_timezone("Asia/Shanghai")
    now = platform_now()
    assert now.tzinfo is not None
    assert now.utcoffset().total_seconds() == 8 * 3600


def test_format_platform_datetime_localizes_naive():
    set_cached_platform_timezone("Asia/Shanghai")
    naive = datetime(2026, 8, 5, 10, 0, 0)
    assert format_platform_datetime(naive) == "2026-08-05 10:00:00"

    aware_utc = pytz.UTC.localize(datetime(2026, 8, 5, 2, 0, 0))
    assert format_platform_datetime(aware_utc) == "2026-08-05 10:00:00"


@pytest.mark.asyncio
async def test_get_platform_timezone_refreshes_from_config():
    clear_platform_timezone_cache()
    with patch(
        "app.services.config_service.ConfigService.get",
        new_callable=AsyncMock,
        return_value="America/New_York",
    ) as mocked:
        tz = await get_platform_timezone()
        assert tz == "America/New_York"
        mocked.assert_awaited()
        assert PLATFORM_TIMEZONE_CONFIG_KEY in str(mocked.await_args)


@pytest.mark.asyncio
async def test_get_platform_timezone_uses_cache_without_db_hit():
    set_cached_platform_timezone("Asia/Singapore")
    with patch(
        "app.services.config_service.ConfigService.get",
        new_callable=AsyncMock,
    ) as mocked:
        tz = await get_platform_timezone()
        assert tz == "Asia/Singapore"
        mocked.assert_not_awaited()
