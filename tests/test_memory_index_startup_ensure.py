"""Startup memory index ensure: recreates schema after Redis restart, never DROP."""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.ai.memory_index_service import maybe_ensure_memory_index_on_startup

pytestmark = pytest.mark.no_infrastructure


@pytest.mark.asyncio
async def test_startup_skips_when_memory_service_disabled():
    with patch(
        "app.services.ai.memory_index_service.MemoryConfigService.get_bool",
        AsyncMock(return_value=False),
    ), patch(
        "app.services.ai.memory_index_service.MemoryIndexService.ensure_index",
        AsyncMock(),
    ) as ensure:
        await maybe_ensure_memory_index_on_startup()
        ensure.assert_not_awaited()


@pytest.mark.asyncio
async def test_startup_ensures_index_when_memory_enabled():
    with patch(
        "app.services.ai.memory_index_service.MemoryConfigService.get_bool",
        AsyncMock(return_value=True),
    ), patch(
        "app.services.ai.memory_index_service.MemoryIndexService.ensure_index",
        AsyncMock(return_value=True),
    ) as ensure, patch(
        "app.services.ai.memory_index_service.MemoryIndexService.index_name",
        AsyncMock(return_value="nanzi:idx:memory:session_summary"),
    ):
        await maybe_ensure_memory_index_on_startup()
        ensure.assert_awaited_once()
