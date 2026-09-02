"""实体关系数据库探测服务的聚焦测试。"""

from typing import Any, Dict, List, Tuple
from unittest.mock import AsyncMock, patch

import pytest

from app.services.metadata_relationship_probe_service import (
    ForeignKeyEvidence,
    MetadataRelationshipProbeService,
    RelationshipProbeOptions,
)
from app.services.metadata_relationship_candidate_service import (
    MetadataRelationshipCandidateService,
)


pytestmark = pytest.mark.no_infrastructure


class _FakeAdapter:
    """按 SQL 关键字返回预置结果的假适配器。"""

    def __init__(self, routes: List[Tuple[str, List[List[Any]]]]):
        self.db_type = "mysql"
        self.routes = routes
        self.executed: List[str] = []

    async def execute_sql(self, sql: str, params=None) -> Dict[str, Any]:
        self.executed.append(sql)
        for keyword, rows in self.routes:
            if keyword in sql:
                return {"columns": [], "items": [list(row) for row in rows]}
        return {"columns": [], "items": []}


def _build_schema_index() -> Dict[str, Dict[str, Any]]:
    """构造 orders/users/payments 的最小 Schema 索引。"""
    table_order, table_index = MetadataRelationshipCandidateService.parse_schema(
        """tables:
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
    )
    return table_index


def _build_candidates(table_index) -> list:
    return MetadataRelationshipCandidateService.build_candidate_pairs(
        list(table_index.keys()),
        table_index,
    )


def test_find_fk_relationships_matches_child_parent_direction():
    """外键方向应转换为与候选表对一致的 left/right 字段。"""
    table_index = _build_schema_index()
    candidates = _build_candidates(table_index)
    foreign_keys = [
        ForeignKeyEvidence(
            constraint_name="fk_payments_order",
            child_table="payments",
            child_columns=("order_id",),
            parent_table="orders",
            parent_columns=("id",),
        )
    ]
    results = MetadataRelationshipProbeService.find_fk_relationships(
        foreign_keys,
        candidates,
    )
    assert len(results) == 1
    result = results[0]
    # 候选表对顺序为 orders 在左，外键子表是 payments，字段方向需要翻转。
    assert (result.left_table, result.right_table) == ("orders", "payments")
    assert (result.left_column, result.right_column) == ("id", "order_id")
    assert result.confidence == 1.0
    assert result.source == "FK"


def test_find_fk_relationships_ignores_unknown_tables():
    """不在候选范围内的外键不应生成关系结论。"""
    table_index = _build_schema_index()
    candidates = _build_candidates(table_index)
    foreign_keys = [
        ForeignKeyEvidence(
            constraint_name="fk_unknown",
            child_table="logs",
            child_columns=("order_id",),
            parent_table="orders",
            parent_columns=("id",),
        )
    ]
    results = MetadataRelationshipProbeService.find_fk_relationships(
        foreign_keys,
        candidates,
    )
    assert results == []


@pytest.mark.asyncio
async def test_probe_candidate_pairs_confirms_by_sampling():
    """高命中率抽样应生成确认结论，并被低命中候选拒绝。"""
    table_index = _build_schema_index()
    candidates = _build_candidates(table_index)
    probe_pairs = [
        pair for pair in candidates
        if {pair.left_table.lower(), pair.right_table.lower()} == {"orders", "payments"}
    ]
    adapter = _FakeAdapter([
        ("GROUP BY", [[1001, 5], [1002, 4], [1003, 3]]),
        ("IN (", [[1001], [1002], [1003]]),
        ("COUNT(DISTINCT", [[100, 95]]),
    ])
    with patch(
        "app.services.metadata_relationship_probe_service.get_adapter",
        new_callable=AsyncMock,
        return_value=adapter,
    ):
        confirmed, stats = await MetadataRelationshipProbeService.probe_candidate_pairs(
            "mysql_main",
            probe_pairs,
            table_index,
            RelationshipProbeOptions(min_child_values=3),
        )
    assert stats["confirmed_pair_count"] == 1
    assert stats["probed_pair_count"] == 1
    assert confirmed[0].source == "PROBE"
    assert confirmed[0].confidence == 0.95
    assert confirmed[0].sampled == 3
    assert confirmed[0].matched == 3
    # 回查 SQL 必须包含抽样字面量，而不是未绑定参数。
    hit_sql = next(sql for sql in adapter.executed if "IN (" in sql)
    assert "1001" in hit_sql and "1003" in hit_sql


@pytest.mark.asyncio
async def test_probe_candidate_pairs_rejects_low_hit_rate():
    """命中率低于下限的候选应被拒绝，不进入 AI 兜底。"""
    table_index = _build_schema_index()
    candidates = _build_candidates(table_index)
    probe_pairs = [
        pair for pair in candidates
        if {pair.left_table.lower(), pair.right_table.lower()} == {"orders", "payments"}
    ]
    adapter = _FakeAdapter([
        ("GROUP BY", [[1001, 5], [1002, 4], [1003, 3]]),
        ("IN (", [[999]]),
    ])
    with patch(
        "app.services.metadata_relationship_probe_service.get_adapter",
        new_callable=AsyncMock,
        return_value=adapter,
    ):
        confirmed, stats = await MetadataRelationshipProbeService.probe_candidate_pairs(
            "mysql_main",
            probe_pairs,
            table_index,
            RelationshipProbeOptions(min_child_values=3),
        )
    assert confirmed == []
    assert stats["confirmed_pair_count"] == 0
    assert stats["rejected_pair_count"] >= 1


@pytest.mark.asyncio
async def test_probe_candidate_pairs_falls_back_when_adapter_missing():
    """数据源不可用应整体降级，并把原因写入诊断统计。"""
    table_index = _build_schema_index()
    candidates = _build_candidates(table_index)
    with patch(
        "app.services.metadata_relationship_probe_service.get_adapter",
        new_callable=AsyncMock,
        side_effect=ValueError("未找到对应的数据源配置"),
    ):
        confirmed, stats = await MetadataRelationshipProbeService.probe_candidate_pairs(
            "missing_source",
            candidates,
            table_index,
        )
    assert confirmed == []
    assert stats["probe_unavailable_reason"] == "data_source_unavailable"


def test_sql_literal_escapes_quotes_and_backslashes():
    """字面量渲染应转义单引号与反斜杠，避免破坏回查 SQL。"""
    render = MetadataRelationshipProbeService._sql_literal
    assert render("o'brien") == "'o''brien'"
    assert render("a\\b") == "'a\\\\b'"
    assert render(10) == "10"
    assert render(None) == "NULL"

