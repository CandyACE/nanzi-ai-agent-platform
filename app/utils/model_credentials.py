"""Credentials helpers for AI model registry entries.

New registry writes are encrypted with the platform Fernet key. Reads remain
backward-compatible with legacy rows that stored the provider key in plaintext
so deployment can migrate without taking existing models offline.
"""

from typing import Optional

from app.utils.encryption import get_api_key_manager

MODEL_CREDENTIAL_PREFIX = "modelkey:v1:"


class ModelCredentialError(ValueError):
    """Raised when a versioned model credential cannot be decrypted."""


def encrypt_model_api_key(api_key: Optional[str]) -> Optional[str]:
    """Return an encrypted, normalized model key or ``None`` for empty input."""
    normalized = (api_key or "").strip()
    if not normalized:
        return None
    encrypted = get_api_key_manager().encrypt_api_key(normalized)
    return f"{MODEL_CREDENTIAL_PREFIX}{encrypted}"


def decrypt_model_api_key(stored_value: Optional[str]) -> Optional[str]:
    """Decrypt a registry key, falling back to legacy plaintext values."""
    normalized = (stored_value or "").strip()
    if not normalized:
        return None

    manager = get_api_key_manager()
    if normalized.startswith(MODEL_CREDENTIAL_PREFIX):
        try:
            return manager.decrypt_api_key(normalized[len(MODEL_CREDENTIAL_PREFIX):])
        except ValueError as exc:
            raise ModelCredentialError("模型 API Key 密文无法解密，请检查 ENCRYPTION_KEY 或重新录入密钥") from exc

    try:
        # Support the unversioned encrypted value written by the first P0
        # rollout before the version prefix was introduced.
        return manager.decrypt_api_key(normalized)
    except ValueError:
        # V16 stored model keys in plaintext. Keep those rows usable until
        # they are edited or explicitly migrated.
        if normalized.startswith("Z0FB"):
            raise ModelCredentialError("模型 API Key 密文无法解密，请检查 ENCRYPTION_KEY 或重新录入密钥")
        return normalized


def is_encrypted_model_api_key(stored_value: Optional[str]) -> bool:
    """Return whether a stored value can be decrypted by the current key."""
    normalized = (stored_value or "").strip()
    if not normalized:
        return False

    try:
        decrypt_model_api_key(normalized)
        return normalized.startswith(MODEL_CREDENTIAL_PREFIX) or normalized.startswith("Z0FB")
    except ModelCredentialError:
        return True
