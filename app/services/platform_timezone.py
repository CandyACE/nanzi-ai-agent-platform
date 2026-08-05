"""平台业务时区：系统配置单一来源，供调度、时间锚点与展示使用。"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import FrozenSet, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pytz

logger = logging.getLogger(__name__)

PLATFORM_TIMEZONE_CONFIG_KEY = "platform_timezone"
DEFAULT_PLATFORM_TIMEZONE = "Asia/Shanghai"

# 系统设置下拉可选；校验时仍允许任意合法 IANA（便于运维扩展）
PLATFORM_TIMEZONE_CHOICES: tuple[str, ...] = (
    "Asia/Shanghai",
    "Asia/Hong_Kong",
    "Asia/Tokyo",
    "Asia/Singapore",
    "UTC",
    "America/Los_Angeles",
    "America/New_York",
    "Europe/London",
)

_cached_tz: Optional[str] = None


def validate_timezone_name(value: Optional[str], *, fallback: str = DEFAULT_PLATFORM_TIMEZONE) -> str:
    """Normalize and validate an IANA timezone name."""
    candidate = str(value or "").strip().lstrip(":")
    if not candidate:
        return fallback
    try:
        ZoneInfo(candidate)
    except ZoneInfoNotFoundError:
        logger.warning("Invalid timezone %r, fallback to %s", candidate, fallback)
        return fallback
    # Ensure pytz also understands it (APScheduler uses pytz)
    try:
        pytz.timezone(candidate)
    except Exception:
        logger.warning("pytz cannot load timezone %r, fallback to %s", candidate, fallback)
        return fallback
    return candidate


def _timezone_from_env() -> Optional[str]:
    for key in ("PLATFORM_TIMEZONE", "TZ"):
        raw = (os.environ.get(key) or "").strip().lstrip(":")
        if not raw:
            continue
        try:
            ZoneInfo(raw)
            pytz.timezone(raw)
            return raw
        except Exception:
            logger.warning("Ignoring invalid %s=%r", key, raw)
    return None


def get_cached_platform_timezone() -> str:
    """Sync read: memory cache → env → default. Does not hit DB."""
    global _cached_tz
    if _cached_tz:
        return _cached_tz
    from_env = _timezone_from_env()
    if from_env:
        _cached_tz = from_env
        return _cached_tz
    _cached_tz = DEFAULT_PLATFORM_TIMEZONE
    return _cached_tz


def set_cached_platform_timezone(value: Optional[str]) -> str:
    """Update in-process cache (e.g. after config save or startup refresh)."""
    global _cached_tz
    _cached_tz = validate_timezone_name(value, fallback=DEFAULT_PLATFORM_TIMEZONE)
    return _cached_tz


def clear_platform_timezone_cache() -> None:
    global _cached_tz
    _cached_tz = None


async def refresh_platform_timezone() -> str:
    """Load platform timezone from system_configs into process cache."""
    from app.services.config_service import ConfigService

    raw = await ConfigService.get(PLATFORM_TIMEZONE_CONFIG_KEY, DEFAULT_PLATFORM_TIMEZONE)
    return set_cached_platform_timezone(raw)


async def get_platform_timezone() -> str:
    """Async accessor: prefer cache, otherwise refresh from ConfigService."""
    if _cached_tz:
        return _cached_tz
    try:
        return await refresh_platform_timezone()
    except Exception as exc:
        logger.warning("Failed to load platform_timezone from config: %s", exc)
        return get_cached_platform_timezone()


def get_platform_tzinfo():
    """Return pytz timezone object for APScheduler / localize."""
    return pytz.timezone(get_cached_platform_timezone())


def platform_now() -> datetime:
    """Timezone-aware 'now' in the platform business timezone."""
    tz = get_platform_tzinfo()
    return datetime.now(tz)


def format_platform_datetime(
    value: Optional[datetime],
    *,
    fmt: str = "%Y-%m-%d %H:%M:%S",
) -> str:
    """Format a datetime in the platform timezone (naive treated as already local wall clock)."""
    if value is None:
        return ""
    tz = get_platform_tzinfo()
    if value.tzinfo is None:
        localized = tz.localize(value)
    else:
        localized = value.astimezone(tz)
    return localized.strftime(fmt)


def allowed_timezone_choices() -> FrozenSet[str]:
    return frozenset(PLATFORM_TIMEZONE_CHOICES)
