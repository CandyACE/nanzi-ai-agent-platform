"""Tests for smart relationship recommendation with table filtering and deduplication."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.metadata_generator import MetadataGeneratorService

pytestmark = pytest.mark.no_infrastructure


@pytest.mark.asyncio
async def test_recommend_relationships_deduplication_and_user_prompt():
    dataset_id = 999
    schema_yaml = """
tables:
  - physical_name: orders
    term: 订单主表
    columns:
      - physical_name: id
        is_primary: true
      - physical_name: user_id
  - physical_name: users
    term: 用户表
    columns:
      - physical_name: id
        is_primary: true
"""

    mock_llm_result = {
        "relationships": [
            {
                "source_table": "orders",
                "target_table": "users",
                "condition": "orders.user_id = users.id",
                "relation_type": "many_to_one",
                "confidence": 0.95,
                "description": "订单关联用户主表"
            },
            {
                "source_table": "orders",
                "target_table": "payments",
                "condition": "orders.id = payments.order_id",
                "relation_type": "one_to_many",
                "confidence": 0.90,
                "description": "订单关联支付流水"
            },
        ]
    }

    mock_redis = AsyncMock()
    # 模拟 Redis 存在近期推荐缓存（已经推荐过 orders <-> users）
    mock_redis.get.return_value = '[{"source_table": "orders", "target_table": "users", "condition": "orders.user_id = users.id"}]'
    mock_redis.setex = AsyncMock()

    with patch("app.core.redis.get_redis", return_value=mock_redis), \
         patch("app.services.metadata_generator.MetadataGeneratorService._save_trace_log", new_callable=AsyncMock), \
         patch("app.services.metadata_generator.AgentConfigProvider.get_configured_llm", new_callable=AsyncMock), \
         patch("app.services.metadata_generator.MetadataGeneratorService._invoke_json", new_callable=AsyncMock, return_value=mock_llm_result) as mock_invoke:

        result = await MetadataGeneratorService.recommend_relationships(
            dataset_id=dataset_id,
            schema_context=schema_yaml,
            user_prompt="重点分析订单与支付流水的核销关联",
            existing_relationships=["orders <-> order_items (orders.id = order_items.order_id)"]
        )

        # 验证 LLM prompt 中包含了 user_prompt 与已存在关系排除
        call_args = mock_invoke.call_args
        system_prompt = call_args[0][2]
        assert "重点分析订单与支付流水的核销关联" in system_prompt
        assert "orders <-> order_items" in system_prompt
        assert "不设置最终总数量上限" in system_prompt
        assert "单批最多 10 条" in system_prompt

        # 验证后置过滤：orders <-> users 被 Redis 缓存去重剔除，仅保留 orders <-> payments
        rels = result.get("relationships", [])
        assert len(rels) == 1
        assert rels[0]["target_table"] == "payments"

        # 验证新推荐项写入了 Redis
        mock_redis.setex.assert_called_once()
        args = mock_redis.setex.call_args[0]
        assert args[0] == f"metadata:rel_rec:recent:{dataset_id}"
        assert args[1] == 600


@pytest.mark.asyncio
async def test_recommend_relationships_merges_multiple_batches_without_total_limit():
    """多批模型结果应合并返回，单批大小不应成为最终结果数量上限。"""
    dataset_id = 1000
    schema_yaml = "tables:\n  - physical_name: orders\n  - physical_name: users\n"
    first_batch = {
        "relationships": [
            {
                "source_table": "orders",
                "target_table": "users",
                "condition": "orders.user_id = users.id",
                "relation_type": "many_to_one",
                "confidence": 0.95,
                "description": "订单关联用户",
            }
        ],
        "has_more": True,
    }
    second_batch = {
        "relationships": [
            {
                "source_table": "orders",
                "target_table": "users",
                "condition": "orders.owner_id = users.id",
                "relation_type": "many_to_one",
                "confidence": 0.82,
                "description": "订单关联负责人",
            }
        ],
        "has_more": False,
    }

    mock_redis = AsyncMock()
    mock_redis.get.return_value = None

    with patch("app.core.redis.get_redis", return_value=mock_redis), \
         patch("app.services.metadata_generator.MetadataGeneratorService._save_trace_log", new_callable=AsyncMock), \
         patch("app.services.metadata_generator.AgentConfigProvider.get_configured_llm", new_callable=AsyncMock), \
         patch(
             "app.services.metadata_generator.MetadataGeneratorService._invoke_json",
             new_callable=AsyncMock,
             side_effect=[first_batch, second_batch],
         ) as mock_invoke:
        result = await MetadataGeneratorService.recommend_relationships(
            dataset_id=dataset_id,
            schema_context=schema_yaml,
        )

    assert len(result["relationships"]) == 2
    assert mock_invoke.await_count == 2
    assert "本次任务已输出关系" in mock_invoke.await_args_list[1].args[0][3]


@pytest.mark.asyncio
async def test_recommend_relationships_keeps_completed_batches_when_next_batch_fails():
    """后续批次解析失败时，应保留已经成功生成的关系。"""
    dataset_id = 1001
    first_batch = {
        "relationships": [
            {
                "source_table": "orders",
                "target_table": "users",
                "condition": "orders.user_id = users.id",
                "relation_type": "many_to_one",
                "confidence": 0.95,
                "description": "订单关联用户",
            }
        ],
        "has_more": True,
    }

    mock_redis = AsyncMock()
    mock_redis.get.return_value = None

    with patch("app.core.redis.get_redis", return_value=mock_redis), \
         patch("app.services.metadata_generator.MetadataGeneratorService._save_trace_log", new_callable=AsyncMock), \
         patch("app.services.metadata_generator.AgentConfigProvider.get_configured_llm", new_callable=AsyncMock), \
         patch(
             "app.services.metadata_generator.MetadataGeneratorService._invoke_json",
             new_callable=AsyncMock,
             side_effect=[first_batch, ValueError("JSON 截断")],
         ):
        result = await MetadataGeneratorService.recommend_relationships(
            dataset_id=dataset_id,
            schema_context="tables:\n  - physical_name: orders\n",
        )

    assert len(result["relationships"]) == 1
    assert result["relationships"][0]["source_table"] == "orders"
