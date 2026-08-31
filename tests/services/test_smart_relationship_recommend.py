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
            }
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
        assert "不设置数量上限" in system_prompt
        assert "最多推荐 30 条" not in system_prompt

        # 验证后置过滤：orders <-> users 被 Redis 缓存去重剔除，仅保留 orders <-> payments
        rels = result.get("relationships", [])
        assert len(rels) == 1
        assert rels[0]["target_table"] == "payments"

        # 验证新推荐项写入了 Redis
        mock_redis.setex.assert_called_once()
        args = mock_redis.setex.call_args[0]
        assert args[0] == f"metadata:rel_rec:recent:{dataset_id}"
        assert args[1] == 600
