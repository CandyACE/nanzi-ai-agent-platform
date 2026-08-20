import pytest
import json
from unittest.mock import MagicMock, AsyncMock, patch
from app.services.ai.memory_service import MemoryService

# --- Mocks ---

@pytest.fixture(scope="function", autouse=True)
async def init_infrastructure():
    """Override infrastructure initialization."""
    with patch("app.core.database.init_db", new_callable=AsyncMock), \
         patch("app.core.database.close_db", new_callable=AsyncMock), \
         patch("app.core.redis.init_redis", new_callable=AsyncMock), \
         patch("app.core.redis.close_redis", new_callable=AsyncMock):
        yield

@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    # Mock Pipeline: redis.pipeline() 返回一个异步上下文管理器
    mock_pipe = AsyncMock()
    mock_pipe.rpush = AsyncMock(return_value=1)
    mock_pipe.ltrim = AsyncMock(return_value=True)
    mock_pipe.expire = AsyncMock(return_value=True)
    mock_pipe.execute = AsyncMock(return_value=[1, True, True])
    # 让 pipeline() 作为异步上下文管理器使用
    mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
    mock_pipe.__aexit__ = AsyncMock(return_value=False)
    redis.pipeline = MagicMock(return_value=mock_pipe)
    # 保留其他方法 Mock（供其他测试用）
    redis.lrange = AsyncMock(return_value=[])
    redis.delete = AsyncMock(return_value=1)
    redis._mock_pipe = mock_pipe  # 暴露 pipe 引用供测试断言
    return redis

# --- Tests ---

@pytest.mark.asyncio
async def test_memory_service_get_key():
    """测试 Redis Key 生成逻辑"""
    service = MemoryService()
    key = service._get_key("user123", "conv456")
    assert key == "conversation:user123:conv456:history"
    
    # Test anonymous
    key_anon = service._get_key(None, "conv789")
    assert "anonymous" in key_anon


@pytest.mark.asyncio
async def test_memory_service_scopes_active_conversation_by_instance():
    service = MemoryService()

    assert service._get_active_conversation_key("user123") == "conversation:user123:active"
    assert (
        service._get_active_conversation_key("user123", "ops-assistant")
        == "conversation:user123:active:ops-assistant"
    )


@pytest.mark.asyncio
async def test_memory_service_reads_and_writes_instance_active_conversation(mock_redis):
    service = MemoryService()
    mock_redis.get.return_value = "conv-1"

    with patch("app.services.ai.memory_service.get_redis", new_callable=AsyncMock) as mock_get_redis:
        mock_get_redis.return_value = mock_redis

        current = await service.get_active_conversation("u1", "ops-assistant")
        await service.set_active_conversation("u1", "conv-2", "ops-assistant")

    assert current == "conv-1"
    mock_redis.get.assert_awaited_once_with("conversation:u1:active:ops-assistant")
    mock_redis.set.assert_awaited_once_with("conversation:u1:active:ops-assistant", "conv-2")

@pytest.mark.asyncio
async def test_memory_service_add_message(mock_redis):
    """测试添加消息（使用 Pipeline）"""
    service = MemoryService()
    
    with patch("app.services.ai.memory_service.get_redis", new_callable=AsyncMock) as mock_get_redis:
        mock_get_redis.return_value = mock_redis
        
        await service.add_message("u1", "c1", "user", "Hello Redis")
        await service.add_message(
            "u1",
            "c1",
            "assistant",
            "回答",
            reasoning_content="模型推理",
            process_timeline=[{"kind": "log", "title": "调用工具: search", "status": "success"}],
        )
        
        pipe = mock_redis._mock_pipe
        
        # 验证 Pipeline 内 RPUSH 被调用且参数正确
        assert pipe.rpush.called
        args, _ = pipe.rpush.call_args_list[0]
        key, val = args
        assert key == "conversation:u1:c1:history"
        msg_data = json.loads(val)
        assert msg_data["role"] == "user"
        assert msg_data["content"] == "Hello Redis"

        _, assistant_val = pipe.rpush.call_args_list[1].args
        assistant_data = json.loads(assistant_val)
        assert assistant_data["reasoning_content"] == "模型推理"
        assert assistant_data["process_timeline"][0]["title"] == "调用工具: search"
        
        # 验证 LTRIM 和 EXPIRE 也在 Pipeline 中被调用
        assert pipe.ltrim.call_count == 2
        assert pipe.expire.call_count == 2
        # 验证 execute 被调用（提交 Pipeline）
        assert pipe.execute.call_count == 2

@pytest.mark.asyncio
async def test_memory_service_get_history(mock_redis):
    """测试获取历史记录及其限额过滤"""
    service = MemoryService(max_history_turns=2) # Max 4 messages
    
    # Mock data in Redis (5 items), in list-index order (oldest first)
    mock_data = [
        json.dumps({"role": "user", "content": f"msg {i}"})
        for i in range(5)
    ]

    def _lrange_side_effect(key, start, end):
        # 模拟 Redis LRange 返回 [start, end]（含端点）区间，end == -1 表示到末尾
        if end == -1 or end >= len(mock_data):
            end = len(mock_data) - 1
        if start < 0:
            start = 0
        if start > end:
            return []
        return mock_data[start : end + 1]

    mock_redis.llen.return_value = len(mock_data)
    mock_redis.lrange.side_effect = _lrange_side_effect

    with patch("app.services.ai.memory_service.get_redis", new_callable=AsyncMock) as mock_get_redis:
        mock_get_redis.return_value = mock_redis
        
        # 1. Fetch with service default limit (4): Redis 端取窗口 [1,4]
        history = await service.get_history("u1", "c1")
        assert len(history) == 4
        assert history[-1]["content"] == "msg 4"
        assert history[0]["content"] == "msg 1"
        
        # 2. Fetch with custom limit (2): Redis 端取窗口 [3,4]
        history_limited = await service.get_history("u1", "c1", limit=2)
        assert len(history_limited) == 2
        assert history_limited[0]["content"] == "msg 3"

@pytest.mark.asyncio
async def test_memory_service_clear_history(mock_redis):
    """测试清理历史记录"""
    service = MemoryService()
    
    with patch("app.services.ai.memory_service.get_redis", new_callable=AsyncMock) as mock_get_redis:
        mock_get_redis.return_value = mock_redis
        
        await service.clear_history("u1", "c1")
        assert mock_redis.delete.call_count == 4
        mock_redis.delete.assert_any_call("conversation:u1:c1:history")
        mock_redis.delete.assert_any_call("conversation:u1:c1:last_data_result")


@pytest.mark.asyncio
async def test_memory_service_update_last_user_message_content(mock_redis):
    service = MemoryService()
    mock_redis.lrange.return_value = [
        json.dumps({"role": "user", "content": "old", "files": [{"url": "a.png"}]}),
        json.dumps({"role": "assistant", "content": "ok"}),
        json.dumps({"role": "user", "content": "latest image", "files": [{"url": "b.png"}]}),
    ]
    mock_redis.lset = AsyncMock(return_value=True)

    with patch("app.services.ai.memory_service.get_redis", new_callable=AsyncMock) as mock_get_redis:
        mock_get_redis.return_value = mock_redis
        updated = await service.update_last_user_message_content(
            "u1",
            "c1",
            "latest image\n\n<vision_sidecar>caption</vision_sidecar>",
        )

    assert updated is True
    mock_redis.lset.assert_awaited_once()
    index, payload = mock_redis.lset.await_args.args[1:]
    assert index == 2
    stored = json.loads(payload)
    assert stored["role"] == "user"
    assert "<vision_sidecar>" in stored["content"]
    assert stored["files"] == [{"url": "b.png"}]


@pytest.mark.asyncio
async def test_memory_service_truncate_history(mock_redis):
    service = MemoryService()
    mock_redis.ltrim = AsyncMock(return_value=True)
    mock_redis.expire = AsyncMock(return_value=True)
    mock_redis.delete = AsyncMock(return_value=1)

    with patch("app.services.ai.memory_service.get_redis", new_callable=AsyncMock) as mock_get_redis:
        mock_get_redis.return_value = mock_redis

        # 截断到保留 2 条
        success = await service.truncate_history("u1", "c1", 2)
        assert success is True
        mock_redis.ltrim.assert_awaited_once_with("conversation:u1:c1:history", 0, 1)

        # 截断到 <= 0 时直接删除
        success_del = await service.truncate_history("u1", "c1", 0)
        assert success_del is True
        mock_redis.delete.assert_awaited_with("conversation:u1:c1:history")
