"""实体关系数据库探测：外键、唯一性元数据与有界抽样验证。

该服务把关系是否存在的判断从 AI 转移到可验证的数据源上：
外键约束是最强证据；没有外键时使用有界抽样检查子表值能否回查父表。
所有探测均为只读查询，任何异常都会转为降级信号而不是推荐失败。
"""

from __future__ import annotations

import asyncio
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


@dataclass(frozen=True)
class RelationshipProbeOptions:
    """有界探测参数，避免大表查询和整体任务失控。"""

    sample_size: int = 1000
    concurrency: int = 8
    per_query_timeout_seconds: float = 3.0
    overall_timeout_seconds: float = 60.0
    max_pairs: int = 300
    confirm_threshold: float = 0.95
    low_confidence_threshold: float = 0.80
    min_parent_cardinality: int = 5
    min_child_values: int = 3


class MetadataRelationshipProbeService:
    """用外键和有界抽样确认候选关系，供关系推荐主流程调用。"""

    _SUPPORTED_TYPES = {"mysql", "postgresql", "sqlserver", "oracle"}

    @staticmethod
    def _quote(identifier: str) -> str:
        """统一使用双引号标识符，由各方言适配层负责兼容转换。"""
        return '"' + str(identifier or "").replace('"', "") + '"'

    @staticmethod
    def _table_for_sql(table_name: str) -> str:
        """物理表名不额外包裹引号，保留 schema.table 语义。"""
        return str(table_name or "").replace('"', "")

    @staticmethod
    async def _run_adapter_sql(adapter: Any, sql: str) -> List[Tuple[Any, ...]]:
        """使用适配器统一查询入口，标准化结果行。"""
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
                "SELECT con.conname, child.relname, a.attname, "
                "parent.relname, ap.attname, u.ordinality "
                "FROM pg_constraint con "
                "JOIN pg_class child ON child.oid = con.conrelid "
                "JOIN pg_class parent ON parent.oid = con.confrelid "
                "JOIN pg_namespace ns ON ns.oid = child.relnamespace "
                "JOIN LATERAL unnest(con.conkey, con.confkey) "
                "WITH ORDINALITY AS u(child_ordinal, parent_ordinal, ordinality) ON TRUE "
                "JOIN pg_attribute a ON a.attrelid = child.oid "
                "AND a.attnum = u.child_ordinal "
                "JOIN pg_attribute ap ON ap.attrelid = parent.oid "
                "AND ap.attnum = u.parent_ordinal "
                "WHERE con.contype = 'f' AND child.relkind IN ('r', 'p') "
                "AND ns.nspname <> 'information_schema' "
                "AND ns.nspname NOT LIKE 'pg\\_%' "
                "ORDER BY child.relname, con.conname, u.ordinality"
            )
        elif db_type == "sqlserver":
            sql = (
                "SELECT fk.name, child_t.name, child_c.name, "
                "parent_t.name, parent_c.name, fkc.constraint_column_id "
                "FROM sys.foreign_keys fk "
                "JOIN sys.foreign_key_columns fkc "
                "ON fkc.constraint_object_id = fk.object_id "
                "JOIN sys.tables child_t "
                "ON child_t.object_id = fkc.parent_object_id "
                "JOIN sys.columns child_c "
                "ON child_c.object_id = fkc.parent_object_id "
                "AND child_c.column_id = fkc.parent_column_id "
                "JOIN sys.tables parent_t "
                "ON parent_t.object_id = fkc.referenced_object_id "
                "JOIN sys.columns parent_c "
                "ON parent_c.object_id = fkc.referenced_object_id "
                "AND parent_c.column_id = fkc.referenced_column_id "
                "ORDER BY child_t.name, fk.name, fkc.constraint_column_id"
            )
        else:
            sql = (
                "SELECT c.constraint_name, c.table_name, cc.column_name, "
                "rc.table_name, rcc.column_name, cc.position "
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
        for fk in foreign_keys:
            child = fk.child_table.split(".")[-1].lower()
            parent = fk.parent_table.split(".")[-1].lower()
            key = tuple(sorted((child, parent)))
            candidate = candidate_lookup.get(key)
            if not candidate or not fk.child_columns or not fk.parent_columns:
                continue
            if child == candidate.left_table.lower():
                child_col = fk.child_columns[0]
                parent_col = fk.parent_columns[0]
            else:
                child_col = fk.parent_columns[0]
                parent_col = fk.child_columns[0]
            results.append(
                ProbePairResult(
                    left_table=candidate.left_table,
                    right_table=candidate.right_table,
                    left_column=child_col,
                    right_column=parent_col,
                    relation_type="many_to_one",
                    confidence=1.0,
                    status="confirmed",
                    reason="数据库外键约束",
                    source="FK",
                )
            )
        return results

    @classmethod
    def _sample_query(
        cls,
        table_name: str,
        column_name: str,
        sample_size: int,
    ) -> str:
        """取子表侧最高频非空值，保证探测输入有界。"""
        table = cls._table_for_sql(table_name)
        column = cls._quote(column_name)
        return (
            f"SELECT {column}, COUNT(*) AS total_count "
            f"FROM {table} WHERE {column} IS NOT NULL "
            f"GROUP BY {column} ORDER BY COUNT(*) DESC "
            f"LIMIT {int(sample_size)}"
        )

    @staticmethod
    def _sql_literal(value: Any) -> str:
        """把抽样值渲染为安全字面量，仅用于等值回查比对。"""
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        if isinstance(value, (int, float)):
            return repr(value)
        text = str(value).replace("\\", "\\\\").replace("'", "''")
        return f"'{text}'"

    @classmethod
    def _parent_hit_query(
        cls,
        parent_table: str,
        parent_column: str,
        sampled_values: Sequence[Any],
    ) -> str:
        """用父表字段等值回查抽样值；值来自子表抽样，直接内联避免方言参数差异。"""
        table = cls._table_for_sql(parent_table)
        column = cls._quote(parent_column)
        literals = ", ".join(cls._sql_literal(value) for value in sampled_values)
        return f"SELECT {column} FROM {table} WHERE {column} IN ({literals})"

    @classmethod
    def _uniqueness_query(cls, table_name: str, column_name: str) -> str:
        """比较总行数和去重数，用于区分一对一与多对一。"""
        table = cls._table_for_sql(table_name)
        column = cls._quote(column_name)
        return (
            f"SELECT COUNT(*) AS total_count, "
            f"COUNT(DISTINCT {column}) AS distinct_count "
            f"FROM {table} WHERE {column} IS NOT NULL"
        )

    @classmethod
    def _type_family(cls, raw_type: Any) -> str:
        """粗粒度类型分族，禁止布尔或未知类型参与键探测。"""
        value = str(raw_type or "").lower()
        if not value:
            return "unknown"
        if any(token in value for token in (
            "int", "decimal", "numeric", "float", "double", "real",
        )):
            return "number"
        if any(token in value for token in ("char", "text", "string", "uuid")):
            return "string"
        if any(token in value for token in ("date", "time")):
            return "datetime"
        if any(token in value for token in ("bool", "bit")):
            return "boolean"
        return "other"

    @classmethod
    async def _probe_pair(
        cls,
        adapter: Any,
        pair: Any,
        left_column: str,
        right_column: str,
        left_type: str,
        right_type: str,
        options: RelationshipProbeOptions,
        semaphore: asyncio.Semaphore,
    ) -> ProbePairResult:
        """探测单个表对，所有异常都转为 unverified 而不是失败。"""

        def make_result(
            status: str,
            reason: str,
            *,
            relation_type: str = "many_to_one",
            confidence: float = 0.0,
            sampled: int = 0,
            matched: int = 0,
            error: Optional[str] = None,
        ) -> ProbePairResult:
            return ProbePairResult(
                left_table=pair.left_table,
                right_table=pair.right_table,
                left_column=left_column,
                right_column=right_column,
                relation_type=relation_type,
                confidence=confidence,
                status=status,
                reason=reason,
                source="PROBE",
                sampled=sampled,
                matched=matched,
                error=error,
            )

        left_family = cls._type_family(left_type)
        right_family = cls._type_family(right_type)
        if left_family in {"boolean", "unknown"} or right_family in {
            "boolean", "unknown",
        }:
            return make_result("rejected", "字段类型不适合作为连接键")
        if left_family != right_family:
            return make_result("rejected", "字段类型族不兼容")

        try:
            async with semaphore:
                sample_rows = await asyncio.wait_for(
                    cls._run_adapter_sql(
                        adapter,
                        cls._sample_query(
                            pair.left_table,
                            left_column,
                            options.sample_size,
                        ),
                    ),
                    timeout=options.per_query_timeout_seconds,
                )
            sampled_values: List[Tuple[Any, int]] = []
            seen_values = set()
            for row in sample_rows[: options.sample_size]:
                value = row[0]
                normalized = str(value)
                if normalized in seen_values:
                    continue
                seen_values.add(normalized)
                sampled_values.append((value, int(row[1] or 1)))
            sampled = len(sampled_values)
            if sampled < options.min_child_values:
                return make_result(
                    "unverified",
                    "子表抽样值过少，无法验证",
                    sampled=sampled,
                )

            async with semaphore:
                hit_rows = await asyncio.wait_for(
                    cls._run_adapter_sql(
                        adapter,
                        cls._parent_hit_query(
                            pair.right_table,
                            right_column,
                            [value for value, _ in sampled_values],
                        ),
                    ),
                    timeout=options.per_query_timeout_seconds,
                )
            parent_values = {str(row[0]) for row in hit_rows if row[0] is not None}
            matched = sum(
                1 for value, _ in sampled_values
                if str(value) in parent_values
            )
            hit_rate = matched / sampled if sampled else 0.0
            if hit_rate < options.low_confidence_threshold:
                return make_result(
                    "rejected",
                    f"抽样命中率 {hit_rate:.2f} 低于阈值",
                    sampled=sampled,
                    matched=matched,
                )

            async with semaphore:
                child_stats = await asyncio.wait_for(
                    cls._run_adapter_sql(
                        adapter,
                        cls._uniqueness_query(pair.left_table, left_column),
                    ),
                    timeout=options.per_query_timeout_seconds,
                )
            async with semaphore:
                parent_stats = await asyncio.wait_for(
                    cls._run_adapter_sql(
                        adapter,
                        cls._uniqueness_query(pair.right_table, right_column),
                    ),
                    timeout=options.per_query_timeout_seconds,
                )
            child_total, child_distinct = cls._parse_stats(child_stats)
            parent_total, parent_distinct = cls._parse_stats(parent_stats)
            if parent_distinct is None or parent_distinct < options.min_parent_cardinality:
                return make_result(
                    "rejected",
                    "父表字段基数过低，疑似状态字段",
                    sampled=sampled,
                    matched=matched,
                )

            child_unique = bool(child_total and child_distinct == child_total)
            parent_unique = bool(parent_total and parent_distinct == parent_total)
            relation_type = "one_to_one" if child_unique and parent_unique else "many_to_one"
            confidence = (
                0.95 if hit_rate >= options.confirm_threshold else 0.80
            )
            return make_result(
                "confirmed",
                f"抽样命中率 {hit_rate:.2f}",
                relation_type=relation_type,
                confidence=confidence,
                sampled=sampled,
                matched=matched,
            )
        except asyncio.TimeoutError as exc:
            return make_result("unverified", "探测超时", error=str(exc))
        except Exception as exc:
            logger.info(
                "关系探测单表对失败: table_pair=%s/%s, error=%s",
                pair.left_table,
                pair.right_table,
                exc,
            )
            return make_result("unverified", "探测异常，转模型兜底", error=str(exc))

    @staticmethod
    def _parse_stats(rows: List[Tuple[Any, ...]]) -> Tuple[Optional[int], Optional[int]]:
        """读取 COUNT 和 COUNT(DISTINCT) 单行结果。"""
        if not rows:
            return None, None
        try:
            return int(rows[0][0] or 0), int(rows[0][1] or 0)
        except (TypeError, ValueError):
            return None, None

    @classmethod
    async def probe_candidate_pairs(
        cls,
        data_source: Optional[str],
        candidate_pairs: Sequence[Any],
        schema_index: Dict[str, Dict[str, Any]],
        options: Optional[RelationshipProbeOptions] = None,
    ) -> Tuple[List[ProbePairResult], Dict[str, Any]]:
        """并发探测候选表对，返回确认结果与诊断统计。"""
        options = options or RelationshipProbeOptions()
        empty_stats = {
            "probed_pair_count": 0,
            "confirmed_pair_count": 0,
            "rejected_pair_count": 0,
            "rejected_reasons": {},
            "unverified_pair_count": 0,
            "probe_duration_ms": 0,
            "probe_unavailable_reason": None,
        }
        ordered_pairs = list(candidate_pairs)[: options.max_pairs]
        if not ordered_pairs:
            return [], empty_stats

        try:
            adapter = await get_adapter(data_source)
            db_type = str(getattr(adapter, "db_type", "") or "").lower()
        except Exception as exc:
            logger.warning(
                "关系探测适配器不可用: data_source=%s, error=%s",
                data_source,
                exc,
                exc_info=True,
            )
            return [], {
                **empty_stats,
                "probe_unavailable_reason": "data_source_unavailable",
            }

        if db_type not in cls._SUPPORTED_TYPES:
            return [], {
                **empty_stats,
                "probe_unavailable_reason": "unsupported_db_type",
            }

        semaphore = asyncio.Semaphore(options.concurrency)
        started_at = asyncio.get_running_loop().time()
        tasks: List[Any] = []
        for pair in ordered_pairs:
            left_columns = {
                str(column.get("name") or ""): column
                for column in (schema_index.get(pair.left_table) or {}).get("columns") or []
            }
            right_columns = {
                str(column.get("name") or ""): column
                for column in (schema_index.get(pair.right_table) or {}).get("columns") or []
            }
            for left_column, right_column in pair.column_pairs:
                tasks.append(
                    cls._probe_pair(
                        adapter,
                        pair,
                        left_column,
                        right_column,
                        str(left_columns.get(left_column, {}).get("type") or ""),
                        str(right_columns.get(right_column, {}).get("type") or ""),
                        options,
                        semaphore,
                    )
                )

        async def run_all() -> List[ProbePairResult]:
            return list(await asyncio.gather(*tasks))

        try:
            all_results = await asyncio.wait_for(
                run_all(),
                timeout=options.overall_timeout_seconds,
            )
            probe_unavailable_reason = None
        except asyncio.TimeoutError:
            logger.warning(
                "关系探测整体超时: data_source=%s, task_count=%s",
                data_source,
                len(tasks),
            )
            all_results = []
            probe_unavailable_reason = "overall_probe_timeout"

        confirmed: Dict[Tuple[str, str], ProbePairResult] = {}
        rejected_reasons: Dict[str, int] = {}
        unverified_count = 0
        for result in all_results:
            pair_key = tuple(sorted((
                result.left_table.lower(),
                result.right_table.lower(),
            )))
            if result.status == "confirmed":
                existing = confirmed.get(pair_key)
                if not existing or result.confidence > existing.confidence:
                    confirmed[pair_key] = result
            elif result.status == "rejected":
                rejected_reasons[result.reason] = (
                    rejected_reasons.get(result.reason, 0) + 1
                )
            else:
                unverified_count += 1

        duration_ms = (
            asyncio.get_running_loop().time() - started_at
        ) * 1000
        logger.info(
            "关系探测完成: data_source=%s, pair_count=%s, confirmed=%s, "
            "unverified=%s, duration_ms=%.2f",
            data_source,
            len(ordered_pairs),
            len(confirmed),
            unverified_count,
            duration_ms,
        )
        return list(confirmed.values()), {
            "probed_pair_count": len(ordered_pairs),
            "confirmed_pair_count": len(confirmed),
            "rejected_pair_count": len(rejected_reasons),
            "rejected_reasons": rejected_reasons,
            "unverified_pair_count": unverified_count,
            "probe_duration_ms": round(duration_ms, 2),
            "probe_unavailable_reason": probe_unavailable_reason,
        }
