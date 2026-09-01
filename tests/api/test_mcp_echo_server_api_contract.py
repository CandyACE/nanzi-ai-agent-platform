from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.portal.endpoints import mcp
from app.models.mcp import McpServer, McpToolCache


pytestmark = pytest.mark.no_infrastructure


def test_echo_test_mcp_creation_route_is_available_and_not_a_user_server():
    route = next(
        route
        for route in mcp.router.routes
        if getattr(route, "path", None) == "/servers/echo-test"
    )

    assert "POST" in route.methods
    assert mcp.ECHO_SERVER_ID
    assert mcp.ECHO_SERVER_NAME == "NanZi Echo 测试 MCP"


def test_echo_creation_contract_is_global_idempotent_and_write_only():
    source = Path("app/api/portal/endpoints/mcp.py").read_text(encoding="utf-8")

    assert 'scope="global"' in source
    assert "fixed_token_encrypted" in source
    assert "user_assertion_private_key_encrypted" in source
    assert "ECHO_TOOL_NAME" in source
    assert "echo_tool_schema()" in source
    assert "只有系统管理员才能创建 Echo 测试 MCP" in source
    assert "Authorization Bearer Token" in source
    assert "fixed_token" not in mcp.McpServerResponse.model_fields
    assert "user_assertion_private_key_encrypted" not in mcp.McpServerResponse.model_fields


def test_main_mounts_echo_streamable_http_mcp():
    source = Path("app/main.py").read_text(encoding="utf-8")

    assert "echo_mcp.streamable_http_app()" in source
    assert 'app.mount("/mcp/echo"' in source
    assert "echo_mcp_lifespan" in source
    assert "async with echo_mcp_lifespan()" in source


@pytest.mark.asyncio
async def test_echo_creation_is_admin_only_and_returns_no_credentials():
    db = MagicMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.execute = AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None))
    manager = MagicMock()
    manager.encrypt_api_key.return_value = "encrypted-value"

    with patch.object(mcp, "get_api_key_manager", return_value=manager), patch.object(
        mcp, "_clear_runtime_tool_cache"
    ):
        response = await mcp.create_echo_test_mcp(
            SimpleNamespace(base_url="https://nanzi.example.com/"),
            db,
            {"role": "admin"},
        )

    assert response.id == mcp.ECHO_SERVER_ID
    assert response.sse_url == "https://nanzi.example.com/mcp/echo/mcp"
    assert response.scope == "global"
    assert response.credential_mode == "fixed_token_signed_user"
    assert response.user_assertion_enabled is True
    assert response.tool_count == 1
    assert "fixed_token_encrypted" not in response.model_dump()
    assert "user_assertion_private_key_encrypted" not in response.model_dump()
    added = [call.args[0] for call in db.add.call_args_list]
    assert any(isinstance(item, McpServer) for item in added)
    assert any(isinstance(item, McpToolCache) and item.is_published for item in added)
    assert manager.encrypt_api_key.call_count == 2


@pytest.mark.asyncio
async def test_echo_creation_rejects_non_admin_before_database_access():
    db = MagicMock()
    db.execute = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await mcp.create_echo_test_mcp(
            SimpleNamespace(base_url="https://nanzi.example.com"),
            db,
            {"role": "user", "user_id": 123},
        )

    assert exc_info.value.status_code == 403
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_echo_creation_reuses_existing_credentials_and_tool():
    server = McpServer(
        id=mcp.ECHO_SERVER_ID,
        server_name="旧 Echo 名称",
        sse_url="http://old/mcp",
        auth_headers="{}",
        credential_mode="static",
        fixed_token_encrypted="existing-token",
        user_assertion_enabled=False,
        user_assertion_header="X-Nanzi-User-Assertion",
        user_assertion_audience="mcp:existing",
        user_assertion_key_id="existing-key",
        user_assertion_issuer="old-issuer",
        user_assertion_private_key_encrypted="existing-private-key",
        enabled_status=0,
        scope="global",
    )
    tool = McpToolCache(
        id="tool-1",
        server_id=mcp.ECHO_SERVER_ID,
        tool_name=mcp.ECHO_TOOL_NAME,
        tool_description="old",
        parameter_schema="{}",
        is_published=False,
        is_available=False,
    )
    db = MagicMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            SimpleNamespace(scalar_one_or_none=lambda: server),
            SimpleNamespace(scalar_one_or_none=lambda: tool),
        ]
    )
    manager = MagicMock()

    with patch.object(mcp, "get_api_key_manager", return_value=manager), patch.object(
        mcp, "_clear_runtime_tool_cache"
    ):
        response = await mcp.create_echo_test_mcp(
            SimpleNamespace(base_url="https://nanzi.example.com"),
            db,
            {"role": "admin"},
        )

    assert response.enabled_status == 1
    assert server.fixed_token_encrypted == "existing-token"
    assert server.user_assertion_private_key_encrypted == "existing-private-key"
    assert server.credential_mode == "fixed_token_signed_user"
    assert tool.is_published is True
    assert tool.is_available is True
    manager.encrypt_api_key.assert_not_called()
