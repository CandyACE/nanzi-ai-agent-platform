"""会话存储与执行链使用的稳定用户身份边界。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class MissingUserIdentityError(ValueError):
    """请求没有可用于会话隔离的可靠用户身份。"""


def require_user_id(value: Any) -> str:
    """提取并归一化稳定用户 ID；缺失时 fail closed。

    ``anonymous`` 不是用户身份，不能作为会话历史、资源范围或压缩记录的
    fallback。调用方可将本异常转换为 HTTP 401，也可让内部执行链直接终止。
    """

    raw_value = value
    if isinstance(value, Mapping):
        raw_value = value.get("user_id") or value.get("id")
    elif not isinstance(value, (str, int)):
        raw_value = getattr(value, "user_id", None) or getattr(value, "id", None)

    normalized = str(raw_value).strip() if raw_value is not None else ""
    if not normalized or normalized.lower() == "anonymous":
        raise MissingUserIdentityError(
            "缺少可靠用户身份，禁止访问或创建会话上下文"
        )
    return normalized


__all__ = ["MissingUserIdentityError", "require_user_id"]
