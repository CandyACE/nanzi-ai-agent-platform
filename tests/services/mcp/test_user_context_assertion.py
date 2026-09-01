import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.services.mcp.user_context_assertion import (
    MAX_CUSTOM_ATTRIBUTES_BYTES,
    issue_user_assertion,
    public_jwks,
    verify_user_assertion,
)


pytestmark = pytest.mark.no_infrastructure


@pytest.fixture()
def key_pair():
    private_key = Ed25519PrivateKey.generate()
    return private_key, private_key.public_key()


def _user_info(extra_data=None):
    return {
        "user_id": "123",
        "user_name": "zhangsan",
        "real_name": "张三",
        "dept_code": "sales",
        "org_path": "/集团/销售部",
        "extra_data": extra_data or json.dumps(
            {"employee_level": "L3", "region_code": "east", "api_key": "drop-me"}
        ),
    }


def _agent_info():
    return {
        "agent_id": "agent-sales-assistant",
        "agent_version_id": "agent-version-2026-01",
        "agent_name": "销售助手",
    }


def test_issue_assertion_contains_minimal_user_and_agent_context(key_pair):
    private_key, public_key = key_pair

    token = issue_user_assertion(
        user_info=_user_info(),
        agent_info=_agent_info(),
        audience="mcp:crm",
        request_id="req-1",
        private_key=private_key,
        key_id="key-1",
    )

    claims = verify_user_assertion(
        token,
        public_key=public_key,
        issuer="nanzi-platform",
        audience="mcp:crm",
    )

    assert claims["iss"] == "nanzi-platform"
    assert claims["aud"] == "mcp:crm"
    assert claims["sub"] == "nanzi:user:123"
    assert claims["user_context"] == {
        "user_id": "123",
        "user_name": "zhangsan",
        "real_name": "张三",
        "dept_code": "sales",
        "org_path": "/集团/销售部",
    }
    assert claims["custom_attributes"] == {
        "employee_level": "L3",
        "region_code": "east",
    }
    assert claims["agent_id"] == "agent-sales-assistant"
    assert claims["agent_version_id"] == "agent-version-2026-01"
    assert claims["agent_name"] == "销售助手"
    assert claims["request_id"] == "req-1"
    assert claims["jti"]
    assert claims["exp"] > claims["iat"]
    assert "tenant_id" not in claims
    assert "scope" not in claims


def test_tampered_assertion_fails_verification(key_pair):
    private_key, public_key = key_pair
    token = issue_user_assertion(
        user_info=_user_info(),
        agent_info=_agent_info(),
        audience="mcp:crm",
        request_id="req-1",
        private_key=private_key,
        key_id="key-1",
    )
    header, payload, signature = token.split(".")
    tampered_payload = jwt.utils.base64url_encode(
        json.dumps({"sub": "nanzi:user:1"}).encode()
    ).decode()
    tampered = ".".join((header, tampered_payload, signature))

    with pytest.raises(jwt.InvalidTokenError):
        verify_user_assertion(
            tampered,
            public_key=public_key,
            issuer="nanzi-platform",
            audience="mcp:crm",
        )


def test_expired_assertion_fails_verification(key_pair):
    private_key, public_key = key_pair
    token = issue_user_assertion(
        user_info=_user_info(),
        agent_info=_agent_info(),
        audience="mcp:crm",
        request_id="req-1",
        private_key=private_key,
        key_id="key-1",
        now=int(time.time()) - 120,
        lifetime_seconds=60,
    )

    with pytest.raises(jwt.ExpiredSignatureError):
        verify_user_assertion(
            token,
            public_key=public_key,
            issuer="nanzi-platform",
            audience="mcp:crm",
        )


def test_verify_user_assertion_requires_complete_user_context_claims(key_pair):
    private_key, public_key = key_pair
    token = issue_user_assertion(
        user_info={"user_id": "123"},
        agent_info={"agent_id": "agent-1"},
        audience="mcp:crm",
        request_id="req-1",
        private_key=private_key,
        key_id="key-1",
    )
    claims = jwt.decode(token, options={"verify_signature": False})
    claims.pop("user_context")
    incomplete_token = jwt.encode(
        claims,
        private_key,
        algorithm="EdDSA",
        headers={"kid": "key-1", "typ": "JWT"},
    )

    with pytest.raises(jwt.InvalidTokenError, match="user_context"):
        verify_user_assertion(
            incomplete_token,
            public_key=public_key,
            audience="mcp:crm",
        )


def test_custom_attributes_reject_reserved_and_sensitive_keys(key_pair):
    private_key, public_key = key_pair
    token = issue_user_assertion(
        user_info=_user_info(
            json.dumps(
                {
                    "user_id": "evil",
                    "agent_id": "evil-agent",
                    "password": "secret",
                    "nested": {"token": "secret", "region": "east"},
                }
            )
        ),
        agent_info=_agent_info(),
        audience="mcp:crm",
        request_id="req-1",
        private_key=private_key,
        key_id="key-1",
    )

    claims = verify_user_assertion(
        token,
        public_key=public_key,
        issuer="nanzi-platform",
        audience="mcp:crm",
    )
    assert claims["custom_attributes"] == {
        "nested": {"region": "east"},
    }
    assert claims["user_context"]["user_id"] == "123"
    assert claims["agent_id"] == "agent-sales-assistant"


def test_custom_attributes_over_limit_are_rejected(key_pair):
    private_key, _ = key_pair
    oversized = json.dumps({"payload": "x" * MAX_CUSTOM_ATTRIBUTES_BYTES})

    with pytest.raises(ValueError, match="custom_attributes"):
        issue_user_assertion(
            user_info=_user_info(oversized),
            agent_info=_agent_info(),
            audience="mcp:crm",
            request_id="req-1",
            private_key=private_key,
            key_id="key-1",
        )


def test_public_jwks_exposes_the_matching_ed25519_public_key(key_pair):
    private_key, _ = key_pair

    jwks = public_jwks(private_key=private_key, key_id="key-1")

    assert jwks["keys"] == [{
        "kty": "OKP",
        "crv": "Ed25519",
        "use": "sig",
        "alg": "EdDSA",
        "kid": "key-1",
        "x": jwks["keys"][0]["x"],
    }]
    assert len(jwks["keys"][0]["x"]) == 43
