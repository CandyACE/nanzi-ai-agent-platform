"""Redis client lifecycle tests."""
from unittest.mock import AsyncMock, patch

import pytest

from app.core import redis as redis_module


pytestmark = pytest.mark.no_infrastructure


@pytest.mark.asyncio
async def test_close_redis_uses_aclose_for_all_clients():
    client = AsyncMock()
    binary_client = AsyncMock()

    with patch.object(redis_module, "redis_client", client), patch.object(
        redis_module, "redis_client_binary", binary_client
    ):
        await redis_module.close_redis()

    client.aclose.assert_awaited_once()
    binary_client.aclose.assert_awaited_once()
    client.close.assert_not_awaited()
    binary_client.close.assert_not_awaited()
