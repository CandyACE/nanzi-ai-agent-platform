"""候选表对分组关系推荐服务的聚焦测试。"""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.metadata_generator import MetadataGeneratorService


pytestmark = pytest.mark.no_infrastructure


def _relationship(
    source_table: str,
    target_table: str,
    condition: str,
    *,
    confidence: float = 0.95,
) -> dict:
    """构造符合关系推荐返回契约的测试数据。"""
    return {
        "source_table": source_table,
        "target_table": target_table,
        "condition": condition,
        "relation_type": "many_to_one",
        "confidence": confidence,
        "description": f"{source_table} 关联 {target_table}",
    }


def _base_patches(mock_redis: AsyncMock):
    """返回不访问数据库和外部模型的通用测试补丁。"""
    return (
        patch("app.core.redis.get_redis", return_value=mock_redis),
        patch(
            "app.services.metadata_generator.MetadataGeneratorService._save_trace_log",
            new_callable=AsyncMock,
        ),
        patch(
            "app.services.metadata_generator.AgentManagerService.get_active_agent_config",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.services.metadata_generator.AgentConfigProvider.get_configured_llm",
            new_callable=AsyncMock,
        ),
    )


@pytest.mark.asyncio
async def test_recommend_relationships_deduplicates_and_validates_group_output():
    """候选组结果应排除近期重复项和不属于真实 Schema 的表。"""
    schema_yaml = """tables:
  - physical_name: orders
    columns:
      - physical_name: id
        type: bigint
        is_primary: true
      - physical_name: user_id
        type: bigint
  - physical_name: users
    columns:
      - physical_name: id
        type: bigint
        is_primary: true
  - physical_name: payments
    columns:
      - physical_name: id
        type: bigint
        is_primary: true
      - physical_name: order_id
        type: bigint
"""
    model_result = {
        "relationships": [
            _relationship("orders", "users", "orders.user_id = users.id"),
            _relationship("orders", "payments", "orders.id = payments.order_id"),
            _relationship("orders", "missing", "orders.id = missing.order_id"),
        ]
    }
    mock_redis = AsyncMock()
    mock_redis.get.return_value = (
        '[{"source_table":"orders","target_table":"users",'
        '"condition":"orders.user_id = users.id"}]'
    )
    patches = _base_patches(mock_redis)

    with patches[0], patches[1], patches[2], patches[3], patch(
        "app.services.metadata_generator.MetadataGeneratorService._invoke_json",
        new_callable=AsyncMock,
        return_value=model_result,
    ) as mock_invoke:
        result = await MetadataGeneratorService.recommend_relationships(
            dataset_id=999,
            schema_context=schema_yaml,
            user_prompt="重点分析订单与支付流水",
            existing_relationships=[
                "orders <-> order_items (orders.id = order_items.order_id)"
            ],
        )

    assert result["relationships"] == [model_result["relationships"][1]]
    assert result["_batch_count"] == 1
    assert result["_stop_reason"] == "all_candidate_groups_scanned"
    assert mock_invoke.await_count == 1
    system_prompt = mock_invoke.await_args.args[2]
    group_prompt = mock_invoke.await_args.args[3]
    assert "重点分析订单与支付流水" in system_prompt
    assert "orders <-> order_items" in system_prompt
    assert "不设置最终关系总数上限" in system_prompt
    assert "candidate_pairs" in group_prompt
    mock_redis.set.assert_awaited_once()


@pytest.mark.asyncio
async def test_recommend_relationships_does_not_follow_model_has_more():
    """候选覆盖由后端分组决定，模型 has_more 不得触发额外调用。"""
    schema_yaml = """tables:
  - physical_name: orders
    columns:
      - physical_name: user_id
        type: bigint
  - physical_name: users
    columns:
      - physical_name: id
        type: bigint
        is_primary: true
"""
    model_result = {
        "relationships": [
            _relationship("orders", "users", "orders.user_id = users.id")
        ],
        "has_more": True,
    }
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    patches = _base_patches(mock_redis)

    with patches[0], patches[1], patches[2], patches[3], patch(
        "app.services.metadata_generator.MetadataGeneratorService._invoke_json",
        new_callable=AsyncMock,
        return_value=model_result,
    ) as mock_invoke:
        result = await MetadataGeneratorService.recommend_relationships(
            dataset_id=1000,
            schema_context=schema_yaml,
        )

    assert len(result["relationships"]) == 1
    assert mock_invoke.await_count == 1
    assert result["_debug"]["candidate_group_count"] == 1
    assert result["_debug"]["candidate_pair_count"] == 1


@pytest.mark.asyncio
async def test_recommend_relationships_keeps_completed_groups_when_later_group_fails():
    """后续候选组失败时应继续保留已经校验通过的关系。"""
    schema_yaml = """tables:
  - physical_name: orders
    columns:
      - physical_name: id
        type: bigint
        is_primary: true
      - physical_name: user_id
        type: bigint
  - physical_name: users
    columns:
      - physical_name: id
        type: bigint
        is_primary: true
  - physical_name: payments
    columns:
      - physical_name: id
        type: bigint
        is_primary: true
  - physical_name: shipments
    columns:
      - physical_name: id
        type: bigint
        is_primary: true
  - physical_name: coupons
    columns:
      - physical_name: id
        type: bigint
        is_primary: true
"""
    first_group = {
        "relationships": [
            _relationship("orders", "users", "orders.user_id = users.id")
        ]
    }
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    progress_events = []
    patches = _base_patches(mock_redis)

    async def collect_progress(payload):
        """保存 SSE 进度负载以验证候选组状态。"""
        progress_events.append(payload)

    with patches[0], patches[1], patches[2], patches[3], patch(
        "app.services.metadata_generator.MetadataGeneratorService._invoke_json",
        new_callable=AsyncMock,
        side_effect=[first_group, ValueError("JSON 截断")],
    ) as mock_invoke:
        result = await MetadataGeneratorService.recommend_relationships(
            dataset_id=1001,
            schema_context=schema_yaml,
            user_prompt="执行跨域完整关系检查",
            progress_callback=collect_progress,
        )

    assert mock_invoke.await_count == 2
    assert result["relationships"] == first_group["relationships"]
    assert result["_stop_reason"] == "partial_group_error"
    assert result["_debug"]["candidate_pair_count"] == 10
    assert result["_debug"]["candidate_group_count"] == 2
    assert result["_debug"]["completed_group_count"] == 1
    assert result["_debug"]["failed_group_count"] == 1
    assert progress_events[-1]["phase"] == "interrupted"
    assert progress_events[-1]["remaining_units"] == 1


@pytest.mark.asyncio
async def test_recommend_relationships_skips_ai_when_no_join_candidate_exists():
    """只有通用 id 且没有实体键线索的表不应触发 AI 调用。"""
    schema_yaml = """tables:
  - physical_name: users
    columns:
      - physical_name: id
        type: bigint
        is_primary: true
  - physical_name: packages
    columns:
      - physical_name: id
        type: bigint
        is_primary: true
  - physical_name: audit_logs
    columns:
      - physical_name: event_uuid
        type: varchar
        is_primary: true
"""
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    patches = _base_patches(mock_redis)

    with patches[0], patches[1], patches[2], patches[3] as mock_get_llm, patch(
        "app.services.metadata_generator.MetadataGeneratorService._invoke_json",
        new_callable=AsyncMock,
    ) as mock_invoke:
        result = await MetadataGeneratorService.recommend_relationships(
            dataset_id=1002,
            schema_context=schema_yaml,
        )

    mock_invoke.assert_not_awaited()
    mock_get_llm.assert_not_awaited()
    assert result["relationships"] == []
    assert result["_debug"]["possible_pair_count"] == 3
    assert result["_debug"]["candidate_pair_count"] == 0
    assert result["_debug"]["candidate_group_count"] == 0
