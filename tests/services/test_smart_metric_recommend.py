"""Smart Metric Recommendation and Deduplication Tests."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.services.metadata_generator import MetadataGeneratorService
from app.services.metadata_service import MetadataService
from app.models.metadata import MetaDataset, MetaTable, MetaRelationship, MetaMetric

pytestmark = pytest.mark.no_infrastructure


@pytest.mark.asyncio
async def test_export_dataset_yaml_with_table_filter():
    """测试按 table_names 过滤导出 Schema YAML"""
    # Mock dataset
    t1 = MetaTable(id=1, dataset_id=10, physical_name="table_a", term="表A", status=1, columns=[])
    t2 = MetaTable(id=2, dataset_id=10, physical_name="table_b", term="表B", status=1, columns=[])
    t3 = MetaTable(id=3, dataset_id=10, physical_name="table_c", term="表C", status=1, columns=[])
    
    r1 = MetaRelationship(
        id=1,
        source_table_id=1, target_table_id=2,
        join_condition="table_a.id = table_b.a_id"
    )
    r1.source_table = "table_a"
    r1.target_table = "table_b"

    mock_ds = MetaDataset(
        id=10, name="ds_test", data_source="default_clickhouse",
        tables=[t1, t2, t3], metrics=[]
    )

    with patch.object(MetadataService, "get_dataset_by_id", new_callable=AsyncMock) as mock_get_ds, \
         patch.object(MetadataService, "get_relationships_by_dataset", new_callable=AsyncMock) as mock_get_rel:
        mock_get_ds.return_value = mock_ds
        mock_get_rel.return_value = [r1]

        # 仅选择 table_a
        chunks = await MetadataService.build_dataset_schema_chunk_contents(
            MagicMock(), dataset_id=10, table_names=["table_a"]
        )
        assert len(chunks) == 1
        assert "table_a" in chunks[0]
        assert "table_b" not in chunks[0]
        assert "table_c" not in chunks[0]


@pytest.mark.asyncio
async def test_recommend_metrics_deduplication_and_user_prompt():
    """测试 10 分钟去重与用户自定义 Prompt 拼装与过滤"""
    dataset_id = 99
    schema_yaml = "dataset: test\ntables:\n  - table_name: metric_table"
    user_prompt = "重点分析机房电量消耗与 PUE 计算"

    # Mock DB existing metric
    existing_metric = MetaMetric(
        id=1, dataset_id=dataset_id,
        name="total_energy", display_name="总能耗",
        calculation_logic="sum(power)"
    )

    # Mock Redis with a recently recommended metric (within 10 min)
    mock_redis = AsyncMock()
    mock_redis.smembers.return_value = {b"avg_pue", "平均PUE".encode("utf-8")}
    mock_redis.sadd = AsyncMock()
    mock_redis.expire = AsyncMock()

    # Mock LLM generation output (contains 1 duplicate and 1 new metric)
    mock_llm_result = {
        "metrics": [
            {
                "name": "avg_pue",
                "display_name": "平均PUE",
                "description": "机房平均PUE",
                "calculation_logic": "avg(pue)",
                "unit": ""
            },
            {
                "name": "monthly_power_trend",
                "display_name": "月度用电趋势",
                "description": "按月统计用电量",
                "calculation_logic": "SELECT toYYYYMM(date) AS m, sum(power) FROM metric_table GROUP BY m",
                "unit": "kWh"
            }
        ]
    }

    with patch("app.core.redis.get_redis", new_callable=AsyncMock) as mock_get_redis, \
         patch("app.services.metadata_generator.AgentConfigProvider.get_configured_llm", new_callable=AsyncMock) as mock_get_llm, \
         patch.object(MetadataGeneratorService, "_save_trace_log", new_callable=AsyncMock), \
         patch.object(MetadataGeneratorService, "_invoke_json", new_callable=AsyncMock) as mock_invoke:

        mock_get_redis.return_value = mock_redis
        mock_get_llm.return_value = MagicMock()
        mock_invoke.return_value = mock_llm_result

        result = await MetadataGeneratorService.recommend_metrics(
            dataset_id=dataset_id,
            schema_context=schema_yaml,
            user_prompt=user_prompt,
            existing_metrics=[existing_metric],
        )

        # 检查 Prompt 中是否注入了 user_prompt 和排除约束
        call_args = mock_invoke.call_args
        system_prompt = call_args[0][2]
        assert "【用户特定业务需求与偏好】" in system_prompt
        assert "重点分析机房电量消耗与 PUE 计算" in system_prompt
        assert "【去重与排除约束（严禁重复推荐）】" in system_prompt
        assert "总能耗" in system_prompt or "total_energy" in system_prompt

        # 检查后置去重：avg_pue / 平均PUE 应被过滤掉，只保留 monthly_power_trend
        assert len(result["metrics"]) == 1
        assert result["metrics"][0]["name"] == "monthly_power_trend"

        # 检查新生成的指标是否写入 Redis 并设置 600s 过期
        mock_redis.sadd.assert_called_once()
        mock_redis.expire.assert_called_once_with(f"metadata:metric_rec:recent:{dataset_id}", 600)
