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
    RelationshipCandidatePair,
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


def test_find_fk_relationships_preserves_all_composite_columns():
    """复合外键应保留全部列对，而不是只输出第一列。"""
    candidate = RelationshipCandidatePair(
        left_table="orders",
        right_table="order_items",
        score=120,
        reasons=("显式外键",),
        column_pairs=(("tenant_id", "tenant_id"), ("id", "order_id")),
    )
    foreign_keys = [
        ForeignKeyEvidence(
            constraint_name="fk_order_items_order",
            child_table="order_items",
            child_columns=("tenant_id", "order_id"),
            parent_table="orders",
            parent_columns=("tenant_id", "id"),
        )
    ]

    results = MetadataRelationshipProbeService.find_fk_relationships(
        foreign_keys,
        [candidate],
    )

    assert len(results) == 1
    assert results[0].column_pairs == (
        ("tenant_id", "tenant_id"),
        ("id", "order_id"),
    )


def test_find_fk_relationships_matches_schema_qualified_tables():
    """外键和候选表都带 schema 时应能正确匹配。"""
    candidate = RelationshipCandidatePair(
        left_table="sales.orders",
        right_table="sales.order_items",
        score=120,
        reasons=("显式外键",),
        column_pairs=(("id", "order_id"),),
    )
    foreign_keys = [
        ForeignKeyEvidence(
            constraint_name="fk_order_items_order",
            child_table="sales.order_items",
            child_columns=("order_id",),
            parent_table="sales.orders",
            parent_columns=("id",),
        )
    ]

    results = MetadataRelationshipProbeService.find_fk_relationships(
        foreign_keys,
        [candidate],
    )

    assert len(results) == 1
    assert (results[0].left_table, results[0].right_table) == (
        "sales.orders",
        "sales.order_items",
    )


def test_find_fk_relationships_does_not_cross_match_different_schemas():
    """两个表名相同但 schema 不同且候选已限定 schema 时不得误匹配。"""
    candidate = RelationshipCandidatePair(
        left_table="hr.orders",
        right_table="hr.order_items",
        score=120,
        reasons=("显式外键",),
        column_pairs=(("id", "order_id"),),
    )
    foreign_keys = [
        ForeignKeyEvidence(
            constraint_name="fk_order_items_order",
            child_table="sales.order_items",
            child_columns=("order_id",),
            parent_table="sales.orders",
            parent_columns=("id",),
        )
    ]

    assert MetadataRelationshipProbeService.find_fk_relationships(
        foreign_keys,
        [candidate],
    ) == []


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
async def test_probe_candidate_pairs_does_not_read_business_rows():
    """关系推荐不得执行抽样、回查或业务表统计 SQL。"""
    table_index = _build_schema_index()
    candidates = _build_candidates(table_index)
    adapter = _FakeAdapter([])

    with patch(
        "app.services.metadata_relationship_probe_service.get_adapter",
        new_callable=AsyncMock,
        return_value=adapter,
    ):
        confirmed, stats = await MetadataRelationshipProbeService.probe_candidate_pairs(
            "mysql_main",
            candidates,
            table_index,
            RelationshipProbeOptions(),
        )

    assert confirmed == []
    assert adapter.executed == []
    assert stats["probe_unavailable_reason"] == "business_row_sampling_disabled"


@pytest.mark.asyncio
async def test_probe_candidate_pairs_does_not_need_data_source_adapter():
    """禁用业务行探测后，不应为候选关系获取数据源适配器。"""
    table_index = _build_schema_index()
    candidates = _build_candidates(table_index)
    with patch(
        "app.services.metadata_relationship_probe_service.get_adapter",
        new_callable=AsyncMock,
        side_effect=ValueError("未找到对应的数据源配置"),
    ) as mock_get_adapter:
        confirmed, stats = await MetadataRelationshipProbeService.probe_candidate_pairs(
            "missing_source",
            candidates,
            table_index,
        )
    assert confirmed == []
    assert stats["probe_unavailable_reason"] == "business_row_sampling_disabled"
    mock_get_adapter.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("db_type", "schema_marker"),
    [
        ("postgresql", "parent_ns.nspname"),
        ("sqlserver", "child_schema.name"),
        ("oracle", "c.owner || '.' || c.table_name"),
    ],
)
async def test_load_foreign_keys_preserves_schema_qualified_names(db_type, schema_marker):
    """支持 schema 的数据库应把 schema 一并返回，避免同名表误匹配。"""
    adapter = _FakeAdapter([])
    adapter.db_type = db_type
    with patch(
        "app.services.metadata_relationship_probe_service.get_adapter",
        new_callable=AsyncMock,
        return_value=adapter,
    ):
        evidence, reason = await MetadataRelationshipProbeService.load_foreign_keys(
            "source",
        )

    assert evidence == []
    assert reason is None
    assert schema_marker in adapter.executed[0]
