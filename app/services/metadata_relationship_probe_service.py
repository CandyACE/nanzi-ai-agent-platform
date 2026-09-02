"""实体关系数据库探测：读取外键等结构化元数据。

该服务把可验证的外键约束作为关系确认的强证据；没有外键时由 AI
根据已导出的字段元数据进行兜底判断。服务只查询数据库系统目录，
不读取业务数据行。
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.services.data_adapter.factory import get_adapter
from app.services.metadata_relationship_candidate_service import (
    MetadataRelationshipCandidateService,
)


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ForeignKeyEvidence:
    """真实库外键约束，列序与约束名一一对应。"""

    constraint_name: str
    child_table: str
    child_columns: Tuple[str, ...]
    parent_table: str
    parent_columns: Tuple[str, ...]


@dataclass
class ProbePairResult:
    """单个候选表对的探测结论，供推荐主流程聚合。"""

    left_table: str
    right_table: str
    left_column: str
    right_column: str
    relation_type: str
    confidence: float
    status: str
    reason: str
    source: str
    sampled: int = 0
    matched: int = 0
    error: Optional[str] = None
    column_pairs: Tuple[Tuple[str, str], ...] = ()


@dataclass(frozen=True)
class RelationshipProbeOptions:
    """关系探测兼容选项；当前只允许元数据探测，不读取业务行。"""

    max_pairs: int = 300


class MetadataRelationshipProbeService:
    """用数据库系统目录中的外键约束确认候选关系。"""

    _SUPPORTED_TYPES = {"mysql", "postgresql", "sqlserver", "oracle"}

    @staticmethod
    async def _run_adapter_sql(adapter: Any, sql: str) -> List[Tuple[Any, ...]]:
        """使用适配器统一查询系统目录，并标准化返回行。"""
        result = await adapter.execute_sql(sql)
        return [tuple(row) for row in result.get("items") or []]

    @classmethod
    async def load_foreign_keys(
        cls,
        data_source: Optional[str],
    ) -> Tuple[List[ForeignKeyEvidence], Optional[str]]:
        """读取真实外键；第二项为不可探测原因，None 表示可探测。"""
        if not data_source:
            return [], "no_data_source"
        try:
            adapter = await get_adapter(data_source)
            db_type = str(getattr(adapter, "db_type", "") or "").lower()
        except Exception as exc:
            logger.warning(
                "关系探测数据源不可用: data_source=%s, error=%s",
                data_source,
                exc,
                exc_info=True,
            )
            return [], "data_source_unavailable"

        if db_type not in cls._SUPPORTED_TYPES:
            return [], "unsupported_db_type"

        if db_type == "mysql":
            sql = (
                "SELECT rc.CONSTRAINT_NAME, kcu.TABLE_NAME, kcu.COLUMN_NAME, "
                "kcu.REFERENCED_TABLE_NAME, kcu.REFERENCED_COLUMN_NAME, "
                "kcu.ORDINAL_POSITION "
                "FROM information_schema.KEY_COLUMN_USAGE kcu "
                "JOIN information_schema.REFERENTIAL_CONSTRAINTS rc "
                "ON rc.CONSTRAINT_SCHEMA = kcu.CONSTRAINT_SCHEMA "
                "AND rc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME "
                "WHERE kcu.TABLE_SCHEMA = DATABASE() "
                "AND kcu.REFERENCED_TABLE_NAME IS NOT NULL "
                "ORDER BY kcu.TABLE_NAME, rc.CONSTRAINT_NAME, kcu.ORDINAL_POSITION"
            )
        elif db_type == "postgresql":
            sql = (
                "SELECT con.conname, ns.nspname || '.' || child.relname, a.attname, "
                "parent_ns.nspname || '.' || parent.relname, ap.attname, u.ordinality "
                "FROM pg_constraint con "
                "JOIN pg_class child ON child.oid = con.conrelid "
                "JOIN pg_class parent ON parent.oid = con.confrelid "
                "JOIN pg_namespace ns ON ns.oid = child.relnamespace "
                "JOIN pg_namespace parent_ns ON parent_ns.oid = parent.relnamespace "
                "JOIN LATERAL unnest(con.conkey, con.confkey) "
                "WITH ORDINALITY AS u(child_ordinal, parent_ordinal, ordinality) ON TRUE "
                "JOIN pg_attribute a ON a.attrelid = child.oid "
                "AND a.attnum = u.child_ordinal "
                "JOIN pg_attribute ap ON ap.attrelid = parent.oid "
                "AND ap.attnum = u.parent_ordinal "
                "WHERE con.contype = 'f' AND child.relkind IN ('r', 'p') "
                "AND ns.nspname <> 'information_schema' "
                "AND ns.nspname NOT LIKE 'pg\\_%' "
                "AND parent_ns.nspname <> 'information_schema' "
                "AND parent_ns.nspname NOT LIKE 'pg\\_%' "
                "ORDER BY ns.nspname, child.relname, con.conname, u.ordinality"
            )
        elif db_type == "sqlserver":
            sql = (
                "SELECT fk.name, child_schema.name + '.' + child_t.name, child_c.name, "
                "parent_schema.name + '.' + parent_t.name, parent_c.name, "
                "fkc.constraint_column_id "
                "FROM sys.foreign_keys fk "
                "JOIN sys.foreign_key_columns fkc "
                "ON fkc.constraint_object_id = fk.object_id "
                "JOIN sys.tables child_t "
                "ON child_t.object_id = fkc.parent_object_id "
                "JOIN sys.schemas child_schema "
                "ON child_schema.schema_id = child_t.schema_id "
                "JOIN sys.columns child_c "
                "ON child_c.object_id = fkc.parent_object_id "
                "AND child_c.column_id = fkc.parent_column_id "
                "JOIN sys.tables parent_t "
                "ON parent_t.object_id = fkc.referenced_object_id "
                "JOIN sys.schemas parent_schema "
                "ON parent_schema.schema_id = parent_t.schema_id "
                "JOIN sys.columns parent_c "
                "ON parent_c.object_id = fkc.referenced_object_id "
                "AND parent_c.column_id = fkc.referenced_column_id "
                "ORDER BY child_schema.name, child_t.name, fk.name, fkc.constraint_column_id"
            )
        else:
            sql = (
                "SELECT c.constraint_name, c.owner || '.' || c.table_name, cc.column_name, "
                "rc.owner || '.' || rc.table_name, rcc.column_name, cc.position "
                "FROM all_constraints c "
                "JOIN all_constraints rc ON rc.owner = c.r_owner "
                "AND rc.constraint_name = c.r_constraint_name "
                "JOIN all_cons_columns cc ON cc.owner = c.owner "
                "AND cc.constraint_name = c.constraint_name "
                "JOIN all_cons_columns rcc ON rcc.owner = rc.owner "
                "AND rcc.constraint_name = rc.constraint_name "
                "WHERE c.constraint_type = 'R' "
                "AND c.owner = SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA') "
                "ORDER BY c.table_name, c.constraint_name, cc.position"
            )

        try:
            rows = await cls._run_adapter_sql(adapter, sql)
            evidence = cls._aggregate_foreign_keys(rows)
            logger.info(
                "关系探测外键加载完成: data_source=%s, db_type=%s, "
                "foreign_key_count=%s",
                data_source,
                db_type,
                len(evidence),
            )
            return evidence, None
        except Exception as exc:
            logger.warning(
                "关系探测外键加载失败: data_source=%s, error=%s",
                data_source,
                exc,
                exc_info=True,
            )
            return [], "foreign_key_query_failed"

    @staticmethod
    def _aggregate_foreign_keys(
        rows: Sequence[Any],
    ) -> List[ForeignKeyEvidence]:
        """按约束名聚合复合外键，确保子表与父表列序一致。"""
        grouped: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for row in rows:
            values = list(row)
            if len(values) < 6:
                continue
            constraint_name = str(values[0] or "")
            child_table = str(values[1] or "")
            child_column = str(values[2] or "")
            parent_table = str(values[3] or "")
            parent_column = str(values[4] or "")
            try:
                ordinal = int(values[5] or 0)
            except (TypeError, ValueError):
                ordinal = 0
            if not all([
                constraint_name,
                child_table,
                parent_table,
                child_column,
                parent_column,
            ]):
                continue
            entry = grouped.setdefault(
                (child_table.lower(), constraint_name.lower()),
                {
                    "constraint_name": constraint_name,
                    "child_table": child_table,
                    "parent_table": parent_table,
                    "child": [],
                    "parent": [],
                },
            )
            entry["child"].append((ordinal, child_column))
            entry["parent"].append((ordinal, parent_column))

        evidence: List[ForeignKeyEvidence] = []
        for entry in grouped.values():
            child_columns = [name for _, name in sorted(entry["child"])]
            parent_columns = [name for _, name in sorted(entry["parent"])]
            if not child_columns or len(child_columns) != len(parent_columns):
                logger.warning(
                    "关系探测外键列数不一致: child_table=%s, constraint=%s",
                    entry["child_table"],
                    entry["constraint_name"],
                )
                continue
            evidence.append(
                ForeignKeyEvidence(
                    constraint_name=entry["constraint_name"],
                    child_table=entry["child_table"],
                    child_columns=tuple(child_columns),
                    parent_table=entry["parent_table"],
                    parent_columns=tuple(parent_columns),
                )
            )
        return evidence

    @classmethod
    def find_fk_relationships(
        cls,
        foreign_keys: Sequence[ForeignKeyEvidence],
        candidate_pairs: Sequence[Any],
    ) -> List[ProbePairResult]:
        """把真实外键匹配到候选表对，直接生成最高置信结论。"""
        results: List[ProbePairResult] = []
        candidate_lookup = {pair.unordered_key: pair for pair in candidate_pairs}
        unqualified_lookup: Dict[Tuple[str, str], List[Any]] = {}
        for pair in candidate_pairs:
            key = tuple(sorted((
                cls._unqualified_table_name(pair.left_table),
                cls._unqualified_table_name(pair.right_table),
            )))
            unqualified_lookup.setdefault(key, []).append(pair)

        for fk in foreign_keys:
            child = cls._normalize_table_name(fk.child_table)
            parent = cls._normalize_table_name(fk.parent_table)
            exact_key = tuple(sorted((child, parent)))
            candidate = candidate_lookup.get(exact_key)
            if candidate is None:
                short_key = tuple(sorted((
                    cls._unqualified_table_name(fk.child_table),
                    cls._unqualified_table_name(fk.parent_table),
                )))
                matching_candidates = unqualified_lookup.get(short_key, [])
                candidate = matching_candidates[0] if len(matching_candidates) == 1 else None
            if not candidate or not fk.child_columns or not fk.parent_columns:
                continue
            if len(fk.child_columns) != len(fk.parent_columns):
                logger.warning(
                    "关系探测外键列数不一致，跳过关系: child_table=%s, parent_table=%s, constraint=%s",
                    fk.child_table,
                    fk.parent_table,
                    fk.constraint_name,
                )
                continue

            left_matches_child = cls._same_table(candidate.left_table, fk.child_table)
            right_matches_parent = cls._same_table(candidate.right_table, fk.parent_table)
            left_matches_parent = cls._same_table(candidate.left_table, fk.parent_table)
            right_matches_child = cls._same_table(candidate.right_table, fk.child_table)
            if left_matches_child and right_matches_parent:
                column_pairs = tuple(zip(fk.child_columns, fk.parent_columns))
            elif left_matches_parent and right_matches_child:
                column_pairs = tuple(zip(fk.parent_columns, fk.child_columns))
            else:
                continue

            left_col, right_col = column_pairs[0]
            results.append(
                ProbePairResult(
                    left_table=candidate.left_table,
                    right_table=candidate.right_table,
                    left_column=left_col,
                    right_column=right_col,
                    relation_type="many_to_one",
                    confidence=1.0,
                    status="confirmed",
                    reason="数据库外键约束",
                    source="FK",
                    column_pairs=column_pairs,
                )
            )
        return results

    @staticmethod
    def _normalize_table_name(table_name: Any) -> str:
        """归一化表名，保留 schema 前缀用于精确匹配。"""
        return str(table_name or "").replace('"', "").strip().lower()

    @classmethod
    def _unqualified_table_name(cls, table_name: Any) -> str:
        return cls._normalize_table_name(table_name).split(".")[-1]

    @classmethod
    def _same_table(cls, left: Any, right: Any) -> bool:
        left_name = cls._normalize_table_name(left)
        right_name = cls._normalize_table_name(right)
        if left_name == right_name:
            return True
        # 只有一侧缺少 schema 时才允许短名匹配，避免跨 schema 误认关系。
        if "." in left_name and "." in right_name:
            return False
        return cls._unqualified_table_name(left_name) == cls._unqualified_table_name(right_name)

    @classmethod
    async def probe_candidate_pairs(
        cls,
        data_source: Optional[str],
        candidate_pairs: Sequence[Any],
        schema_index: Dict[str, Dict[str, Any]],
        options: Optional[RelationshipProbeOptions] = None,
    ) -> Tuple[List[ProbePairResult], Dict[str, Any]]:
        """兼容旧调用方，但明确禁止读取业务行，统一交给 AI 兜底。"""
        options = options or RelationshipProbeOptions()
        ordered_pairs = list(candidate_pairs)[: options.max_pairs]
        return [], {
            "probed_pair_count": 0,
            "confirmed_pair_count": 0,
            "rejected_pair_count": 0,
            "rejected_reasons": {},
            "unverified_pair_count": len(ordered_pairs),
            "probe_duration_ms": 0,
            "probe_unavailable_reason": "business_row_sampling_disabled",
        }
