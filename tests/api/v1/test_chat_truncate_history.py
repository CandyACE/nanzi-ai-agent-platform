import pytest
from fastapi import HTTPException
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.dependencies import require_api_key
from app.api.v1.endpoints.chat import TruncateHistoryRequest, truncate_history_endpoint

pytestmark = pytest.mark.no_infrastructure


@pytest.mark.asyncio
async def test_truncate_history_endpoint_success():
    fake_user = {
        "user_id": 1,
        "user_name": "test_user",
        "role": "user",
    }
    app.dependency_overrides[require_api_key] = lambda: fake_user

    try:
        with patch("app.services.ai.memory_service.memory_service.truncate_history", new_callable=AsyncMock) as mock_truncate:
            mock_truncate.return_value = True

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                res = await client.post(
                    "/api/v1/chat/history/truncate",
                    json={"conversation_id": "conv-test-1", "keep_count": 2},
                )

            assert res.status_code == 200
            data = res.json()
            assert data["code"] == 200
            assert data["data"]["success"] is True
            assert data["data"]["keep_count"] == 2
            mock_truncate.assert_awaited_once_with(
                user_id="1",
                conversation_id="conv-test-1",
                keep_count=2,
            )
    finally:
        app.dependency_overrides.pop(require_api_key, None)


@pytest.mark.asyncio
async def test_truncate_history_endpoint_fails_closed_when_redis_is_unavailable():
    fake_user = {
        "user_id": 1,
        "user_name": "test_user",
        "role": "user",
    }
    app.dependency_overrides[require_api_key] = lambda: fake_user

    try:
        with patch(
            "app.services.ai.memory_service.memory_service.truncate_history",
            new_callable=AsyncMock,
        ) as mock_truncate:
            mock_truncate.return_value = False

            db = MagicMock()
            db_result = MagicMock()
            db_result.scalars.return_value.all.return_value = []
            db.execute = AsyncMock(return_value=db_result)
            with pytest.raises(HTTPException) as exc_info:
                await truncate_history_endpoint(
                    TruncateHistoryRequest(conversation_id="conv-test-1", keep_count=2),
                    request=None,
                    user_info=fake_user,
                    db=db,
                )

            assert exc_info.value.status_code == 503
            mock_truncate.assert_awaited_once()
    finally:
        app.dependency_overrides.pop(require_api_key, None)
