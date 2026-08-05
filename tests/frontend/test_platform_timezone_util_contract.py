"""前端契约：platformTimezone 工具对 naive/aware 时间的格式化行为。"""

from pathlib import Path

import pytest

pytestmark = pytest.mark.no_infrastructure

ROOT = Path(__file__).resolve().parents[2]
SRC = (ROOT / "frontend/src/utils/platformTimezone.ts").read_text(encoding="utf-8")


def test_platform_timezone_util_handles_naive_shanghai_offset():
    assert "+08:00" in SRC
    assert "Asia/Shanghai" in SRC
    assert "Intl.DateTimeFormat" in SRC
    assert "timeZone: tz" in SRC


def test_main_bootstraps_public_timezone():
    main = (ROOT / "frontend/src/main.ts").read_text(encoding="utf-8")
    assert "platform_timezone" in main
    assert "setPlatformTimezone" in main
