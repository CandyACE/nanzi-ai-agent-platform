import pytest

from app.services.task_notification_channels import (
    build_notification_delivery_supplement,
    channels_from_task_config,
    merge_notification_channels_into_config,
    normalize_notification_channels,
)


pytestmark = pytest.mark.no_infrastructure


def test_normalize_notification_channels_dedupes_and_filters():
    assert normalize_notification_channels(["portal", "PORTAL", "fax", "dingtalk"]) == [
        "portal",
        "dingtalk",
    ]
    assert normalize_notification_channels(None) == []
    assert normalize_notification_channels("portal") == []


def test_channels_from_task_config_and_merge_preserve_metrics():
    assert channels_from_task_config({"notification_channels": ["email", "portal"]}) == [
        "email",
        "portal",
    ]
    merged = merge_notification_channels_into_config(
        {"task_metrics": {"trigger_count": 2}},
        ["portal", "wechat_work"],
    )
    assert merged["task_metrics"]["trigger_count"] == 2
    assert merged["notification_channels"] == ["portal", "wechat_work"]

    cleared = merge_notification_channels_into_config(merged, [])
    assert "notification_channels" not in cleared
    assert cleared["task_metrics"]["trigger_count"] == 2


def test_build_notification_delivery_supplement_lists_channels_and_scheduler_owns_delivery():
    text = build_notification_delivery_supplement(["portal", "dingtalk"])
    assert "【结果通知说明】" in text
    assert "TaskCenter 统一投递" in text
    assert "站内消息" in text
    assert "钉钉" in text
    assert "无需、也不应调用" in text
    assert "send_portal_notification" in text
    assert "禁止在回复正文中提及" in text
    assert "禁止夹带中间思考" in text
    assert build_notification_delivery_supplement([]) == ""
