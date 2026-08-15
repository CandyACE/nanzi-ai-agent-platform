"""Sanitize client-provided business context at the authentication boundary."""

from collections.abc import Mapping
from typing import Any


AUTHENTICATED_IDENTITY_KEYS = frozenset(
    {
        "user_id",
        "user_name",
        "username",
        "real_name",
        "user_role",
        "role",
        "role_name",
        "is_admin",
        "account_id",
        "department",
        "dept_name",
        "dept_code",
        "org_path",
        "user_dimensions",
        "user_info",
        "user",
        "current_user",
        "authenticated_user",
        "auth_user",
        "permissions",
        "permission",
        "permission_ids",
        "tenant_id",
        "tenant",
        "tenant_name",
        "org_id",
        "organization_id",
        "organization",
        "is_superuser",
        "is_staff",
        "auth_id",
        "auth_user_id",
        "api_key",
        "token",
        "access_token",
        "authorization",
    }
)


def _is_authenticated_identity_key(key: object) -> bool:
    return str(key).strip().lower() in AUTHENTICATED_IDENTITY_KEYS


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _sanitize_value(item)
            for key, item in value.items()
            if not _is_authenticated_identity_key(key)
        }
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    return value


def sanitize_business_context(value: Any) -> dict[str, Any]:
    """Keep business fields while recursively removing auth-shaped fields."""
    sanitized = _sanitize_value(value)
    return sanitized if isinstance(sanitized, dict) else {}


def sanitize_injected_context(value: Any) -> dict[str, Any]:
    """Sanitize the client-provided runtime context without changing server auth data."""
    if not isinstance(value, Mapping):
        return {}

    sanitized: dict[str, Any] = {}
    for key, item in value.items():
        normalized_key = str(key).strip().lower()
        if _is_authenticated_identity_key(normalized_key):
            continue
        if normalized_key == "business_context":
            sanitized["business_context"] = sanitize_business_context(item)
            continue
        sanitized[str(key)] = _sanitize_value(item)
    return sanitized
