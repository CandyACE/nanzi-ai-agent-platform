import uuid
import pytest
from httpx import AsyncClient
from app.services.auth_service import AuthService
from app.core.redis import get_redis


@pytest.mark.asyncio
async def test_embed_ticket_lifecycle(client: AsyncClient, db_session):
    """
    测试 Embed Ticket 完整生命周期：
    1. 签发 Ticket (POST /api/v1/embed/tickets)
    2. 兑换 Session Token (POST /api/v1/embed/tickets/exchange)
    3. 防重放测试 (同一 Ticket 无法兑换两次)
    4. Session Token 鉴权与滑动续期能力验证 (/api/portal/auth/me)
    """
    suffix = uuid.uuid4().hex[:8]
    # 1. 准备测试用户与操作人 Key
    admin_name = f"ticket_adm_{suffix}"
    admin_key = await AuthService.generate_api_key(
        user_name=admin_name, role="admin", db=db_session
    )

    target_user_name = f"ticket_user_{suffix}"
    target_key = await AuthService.generate_api_key(
        user_name=target_user_name,
        real_name="测试员工张三",
        role="user",
        db=db_session,
    )

    # 2. 服务端代表 target_user_name 签发 Ticket
    ticket_resp = await client.post(
        "/api/v1/embed/tickets",
        json={
            "username": target_user_name,
            "agent_id": "sys-agent-chatbi",
            "expires_in": 300,
        },
        headers={"X-API-Key": admin_key},
    )
    assert ticket_resp.status_code == 200
    ticket_data = ticket_resp.json()
    assert ticket_data["code"] == 200
    assert "ticket" in ticket_data["data"]
    ticket_str = ticket_data["data"]["ticket"]
    assert ticket_str.startswith("emt_")
    assert ticket_data["data"]["target_user"]["user_name"] == target_user_name

    # 3. 前端 iframe 调用兑换接口换取 Session Token
    exchange_resp = await client.post(
        "/api/v1/embed/tickets/exchange",
        json={"ticket": ticket_str},
    )
    assert exchange_resp.status_code == 200
    session_data = exchange_resp.json()
    assert session_data["code"] == 200
    assert "session_token" in session_data["data"]
    session_token = session_data["data"]["session_token"]
    assert session_token.startswith("emb_ses_")
    assert session_data["data"]["user_info"]["user_name"] == target_user_name
    assert session_data["data"]["user_info"]["real_name"] == "测试员工张三"

    # 4. 防重放校验：再次使用该 ticket 兑换应立即失败 (400)
    replay_resp = await client.post(
        "/api/v1/embed/tickets/exchange",
        json={"ticket": ticket_str},
    )
    assert replay_resp.status_code == 400
    assert "not found" in replay_resp.text.lower() or "expired" in replay_resp.text.lower()

    # 5. 使用兑换出的 session_token 调用受保护接口验证鉴权
    me_resp = await client.get(
        "/api/portal/auth/me",
        headers={"X-API-Key": session_token},
    )
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["data"]["user_name"] == target_user_name
    assert me_data["data"]["real_name"] == "测试员工张三"

    # 6. 验证滑动续期：请求后 Redis TTL 应被维持在 ~7200 秒
    r = await get_redis()
    if r:
        from app.utils.encryption import get_api_key_manager

        manager = get_api_key_manager()
        h = manager.hash_api_key(session_token)
        ttl = await r.ttl(f"auth:api_key:{h}")
        assert ttl > 7000  # 接近 7200 秒


@pytest.mark.asyncio
async def test_embed_ticket_invalid_user_and_token(client: AsyncClient, db_session):
    """
    测试边界与异常场景：
    - 未授权的普通用户调用签发接口报错 403
    - 管理员调用但目标用户不存在时报错 404
    - 伪造 ticket 兑换报错 400
    """
    suffix = uuid.uuid4().hex[:8]
    # 1. 普通用户默认无 V1 接口权限，应返回 403
    op_name = f"ticket_op_{suffix}"
    op_key = await AuthService.generate_api_key(
        user_name=op_name, role="user", db=db_session
    )
    unauth_resp = await client.post(
        "/api/v1/embed/tickets",
        json={"username": "non_existent_user_999"},
        headers={"X-API-Key": op_key},
    )
    assert unauth_resp.status_code == 403

    # 2. 管理员调用但目标用户不存在，应返回 404
    admin_name = f"ticket_adm404_{suffix}"
    admin_key = await AuthService.generate_api_key(
        user_name=admin_name, role="admin", db=db_session
    )
    not_found_resp = await client.post(
        "/api/v1/embed/tickets",
        json={"username": "non_existent_user_999"},
        headers={"X-API-Key": admin_key},
    )
    assert not_found_resp.status_code == 404

    # 3. 伪造 Ticket 兑换，应返回 400
    bad_resp = await client.post(
        "/api/v1/embed/tickets/exchange",
        json={"ticket": "emt_fake_ticket_123"},
    )
    assert bad_resp.status_code == 400
