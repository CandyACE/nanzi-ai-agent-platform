"""TaskCenter 结果通知渠道：与 UI / create_recurring_task / 调度提示词补充同源。"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence

NOTIFICATION_CHANNELS_KEY = "notification_channels"

# channel_id -> (tool_name, 中文标签, 调用提示)
CHANNEL_SPECS: Dict[str, tuple[str, str, str]] = {
    "portal": (
        "send_portal_notification",
        "站内消息",
        "调用 send_portal_notification(title, content, level=info) 写入门户铃铛站内信",
    ),
    "dingtalk": (
        "send_dingtalk_message",
        "钉钉",
        "调用 send_dingtalk_message(title, content)；凭据来自个人中心→消息通知，勿再索要 webhook",
    ),
    "wechat_work": (
        "send_wechat_work_message",
        "企业微信",
        "调用 send_wechat_work_message(content)；凭据来自个人中心→消息通知，勿再索要 webhook",
    ),
    "email": (
        "send_email",
        "邮件",
        "调用 send_email(to_email, subject, content)；SMTP 与收件人来自个人中心→消息通知，勿再索要服务器配置",
    ),
}

VALID_CHANNEL_IDS = frozenset(CHANNEL_SPECS.keys())


def normalize_notification_channels(raw: Any) -> List[str]:
    if not isinstance(raw, (list, tuple)):
        return []
    seen = set()
    result: List[str] = []
    for item in raw:
        channel = str(item or "").strip().lower()
        if channel in VALID_CHANNEL_IDS and channel not in seen:
            seen.add(channel)
            result.append(channel)
    return result


def channels_from_task_config(config: Optional[Dict[str, Any]]) -> List[str]:
    if not isinstance(config, dict):
        return []
    return normalize_notification_channels(config.get(NOTIFICATION_CHANNELS_KEY))


def merge_notification_channels_into_config(
    config: Optional[Dict[str, Any]],
    channels: Optional[Sequence[str]],
) -> Dict[str, Any]:
    merged = dict(config or {})
    normalized = normalize_notification_channels(channels)
    if normalized:
        merged[NOTIFICATION_CHANNELS_KEY] = normalized
    else:
        merged.pop(NOTIFICATION_CHANNELS_KEY, None)
    return merged


def build_notification_delivery_supplement(channels: Iterable[str]) -> str:
    normalized = normalize_notification_channels(list(channels))
    if not normalized:
        return ""
    labels = [CHANNEL_SPECS[channel][1] for channel in normalized]
    channel_list = "、".join(labels)
    return "\n".join(
        [
            "【结果通知说明】",
            f"任务结束后将由 TaskCenter 统一投递结果到已勾选渠道（{channel_list}）。",
            "你无需、也不应调用 send_portal_notification / send_dingtalk_message / send_wechat_work_message / send_email 等通知工具。",
            "请把完整分析结论写在最终回复正文中（含关键数据解读）；系统会结合查数工具结果一并投递。",
            "严禁在分析未完成、仅输出“查询成功/让我再补充…”等半截话术时结束本轮。",
        ]
    )
