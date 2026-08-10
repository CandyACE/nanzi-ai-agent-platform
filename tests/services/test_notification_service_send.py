"""外部通知渠道发送辅助逻辑：收件人解析、按渠道截断、传输失败重试。"""

import pytest

from app.services.notification_service import (
    NotificationService,
    _send_with_retries,
    _truncate_utf8,
    _SEND_RETRY_DELAYS_SEC,
    _WECHAT_WORK_MAX_BYTES,
)

pytestmark = pytest.mark.no_infrastructure


def test_parse_email_recipients_supports_mixed_separators():
    parsed = NotificationService.parse_email_recipients("a@x.com, b@y.com; c@z.com，d@w.com；e@v.com")
    assert parsed == ["a@x.com", "b@y.com", "c@z.com", "d@w.com", "e@v.com"]


def test_parse_email_recipients_filters_invalid_entries():
    assert NotificationService.parse_email_recipients(None) == []
    assert NotificationService.parse_email_recipients("") == []
    assert NotificationService.parse_email_recipients("not-an-email, ,;") == []
    assert NotificationService.parse_email_recipients("  ok@x.com  ") == ["ok@x.com"]


def test_truncate_utf8_keeps_short_text_untouched():
    assert _truncate_utf8("hello", 100) == "hello"


def test_truncate_utf8_respects_byte_limit_for_multibyte_text():
    text = "数" * 3000  # 每字 3 字节，远超企业微信 4096 字节上限
    truncated = _truncate_utf8(text, _WECHAT_WORK_MAX_BYTES)
    assert len(truncated.encode("utf-8")) <= _WECHAT_WORK_MAX_BYTES
    assert truncated.endswith("（内容超出渠道长度限制，已截断）")


@pytest.mark.asyncio
async def test_send_with_retries_retries_on_transport_exception(monkeypatch):
    import app.services.notification_service as ns

    async def no_sleep(_):
        return None

    monkeypatch.setattr(ns.asyncio, "sleep", no_sleep)

    attempts = []

    async def flaky_send():
        attempts.append(1)
        if len(attempts) < 2:
            raise ConnectionError("network down")
        return True, ""

    ok, err = await _send_with_retries(flaky_send, channel="dingtalk")
    assert ok is True
    assert err == ""
    assert len(attempts) == 2


@pytest.mark.asyncio
async def test_send_with_retries_does_not_retry_business_errors():
    attempts = []

    async def rejected_send():
        attempts.append(1)
        return False, "invalid webhook (Code: 300001)"

    ok, err = await _send_with_retries(rejected_send, channel="wechat_work")
    assert ok is False
    assert "300001" in err
    assert len(attempts) == 1


@pytest.mark.asyncio
async def test_send_with_retries_gives_up_after_max_attempts(monkeypatch):
    import app.services.notification_service as ns

    async def no_sleep(_):
        return None

    monkeypatch.setattr(ns.asyncio, "sleep", no_sleep)

    attempts = []

    async def always_broken():
        attempts.append(1)
        raise TimeoutError("timeout")

    ok, err = await _send_with_retries(always_broken, channel="email")
    assert ok is False
    assert "timeout" in err
    assert len(attempts) == len(_SEND_RETRY_DELAYS_SEC) + 1
