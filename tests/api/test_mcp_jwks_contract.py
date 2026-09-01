import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.main import get_mcp_user_assertion_jwks


pytestmark = pytest.mark.no_infrastructure


@pytest.mark.asyncio
async def test_jwks_endpoint_returns_only_the_configured_public_key(monkeypatch):
    private_key = Ed25519PrivateKey.generate()
    server = type(
        "McpServerStub",
        (),
        {
            "user_assertion_enabled": True,
            "user_assertion_key_id": "crm-key-1",
        },
    )()

    class Result:
        def scalar_one_or_none(self):
            return server

    class Db:
        async def execute(self, _statement):
            return Result()

    monkeypatch.setattr(
        "app.services.mcp.mcp_auth_policy.load_mcp_private_key",
        lambda _server: private_key,
    )

    response = await get_mcp_user_assertion_jwks("server-1", Db())

    assert response["keys"][0]["kid"] == "crm-key-1"
    assert response["keys"][0]["alg"] == "EdDSA"
    assert response["keys"][0]["use"] == "sig"
    assert "d" not in response["keys"][0]


@pytest.mark.asyncio
async def test_jwks_endpoint_is_unavailable_without_signing_key(monkeypatch):
    server = type(
        "McpServerStub",
        (),
        {
            "user_assertion_enabled": True,
            "user_assertion_key_id": "crm-key-1",
        },
    )()

    class Result:
        def scalar_one_or_none(self):
            return server

    class Db:
        async def execute(self, _statement):
            return Result()

    monkeypatch.setattr(
        "app.services.mcp.mcp_auth_policy.load_mcp_private_key", lambda _server: None
    )

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await get_mcp_user_assertion_jwks("server-1", Db())

    assert getattr(exc_info.value, "status_code", None) == 404
