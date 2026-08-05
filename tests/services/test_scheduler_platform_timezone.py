"""调度 Cron 显式使用平台时区。"""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from apscheduler.triggers.cron import CronTrigger

from app.services.platform_timezone import clear_platform_timezone_cache, set_cached_platform_timezone

pytestmark = pytest.mark.no_infrastructure


@pytest.fixture(autouse=True)
def _reset_tz():
    clear_platform_timezone_cache()
    yield
    clear_platform_timezone_cache()


def test_agent_task_cron_next_run_respects_shanghai():
    set_cached_platform_timezone("Asia/Shanghai")
    trigger = CronTrigger.from_crontab("0 8 * * *", timezone="Asia/Shanghai")
    # 2026-08-04 10:00 Shanghai → next should be 2026-08-05 08:00 Shanghai
    base = datetime(2026, 8, 4, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    nxt = trigger.get_next_fire_time(None, base)
    assert nxt is not None
    assert nxt.hour == 8
    assert nxt.minute == 0
    assert nxt.utcoffset().total_seconds() == 8 * 3600


def test_agent_task_cron_next_run_respects_utc_when_configured():
    set_cached_platform_timezone("UTC")
    trigger = CronTrigger.from_crontab("0 8 * * *", timezone="UTC")
    base = datetime(2026, 8, 4, 10, 0, tzinfo=ZoneInfo("UTC"))
    nxt = trigger.get_next_fire_time(None, base)
    assert nxt is not None
    assert nxt.hour == 8
    assert nxt.utcoffset().total_seconds() == 0
