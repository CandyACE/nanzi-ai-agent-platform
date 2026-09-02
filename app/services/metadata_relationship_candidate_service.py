"""元数据实体关系候选表对解析、评分、分组与结果校验。"""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import yaml


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RelationshipCandidatePair:
    """等待 AI 做最终语义判断的一对物理表。"""

    left_table: str
    right_table: str
    score: int
    reasons: Tuple[str, ...]
    column_pairs: Tuple[Tuple[str, str], ...] = ()

    @property
    def unordered_key(self) -> Tuple[str, str]:
        """返回与方向无关的候选表对键。"""
        return tuple(sorted((self.left_table.lower(), self.right_table.lower())))

    def to_prompt_dict(self) -> Dict[str, Any]:
        """生成不包含内部实现细节的模型候选描述。"""
        return {
            "left_table": self.left_table,
            "right_table": self.right_table,
            "evidence": list(self.reasons),
            "candidate_columns": [
                {
                    "left_column": left_column,
                    "right_column": right_column,
                }
                for left_column, right_column in self.column_pairs
            ],
        }


@dataclass(frozen=True)
class RelationshipCandidateGroup:
    """一次模型调用需要完成判断的候选表对集合。"""

    pairs: Tuple[RelationshipCandidatePair, ...]
    table_names: Tuple[str, ...]


@dataclass(frozen=True)
class RelationshipCandidateBuildResult:
    """候选构建结果及智能策略的限量诊断。"""

    pairs: Tuple[RelationshipCandidatePair, ...]
    smart_candidate_pair_count: int
    truncated_pair_count: int


class MetadataRelationshipCandidateService:
    """构建高召回关系候选，并对 AI 输出执行确定性校验。"""

    _SCHEMA_HEADER_PATTERN = re.compile(
        r"^---\s*\[Schema:\d+\]\s+([^\n]+?)\s*---\s*$",
        flags=re.IGNORECASE | re.MULTILINE,
    )
    _KEY_SUFFIXES = {"id", "code", "no", "num", "number", "key", "uuid"}
    _TECHNICAL_PREFIXES = {
        "ny", "tb", "tbl", "dim", "fact", "ods", "dwd", "dws", "app", "src",
    }
    _IGNORED_TABLE_TOKENS = {
        "tbl", "table", "data", "info", "record", "detail", "log", "map",
        "mapping", "rel", "rl",
    }
    _RELATION_TYPES = {"one_to_one", "one_to_many", "many_to_one"}
    _SMART_KEY_SUFFIXES = _KEY_SUFFIXES | {"ref", "reference"}

    @staticmethod
    def _identifier_tokens(value: Any) -> List[str]:
        """拆分英文物理标识符，并对常见复数形式做轻量归一化。"""
        text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(value or "")).lower()
        raw_tokens = re.findall(r"[a-z0-9]+", text)
        tokens: List[str] = []
        for token in raw_tokens:
            if token.endswith("ies") and len(token) > 4:
                token = f"{token[:-3]}y"
            elif token.endswith("s") and not token.endswith("ss") and len(token) > 3:
                token = token[:-1]
            tokens.append(token)
        return list(dict.fromkeys(tokens))

    @classmethod
    def _table_aliases(cls, table_name: str) -> set[str]:
        """生成实体表名及复合后缀别名，并剔除技术前缀。"""
        raw_tokens = [
            token for token in cls._identifier_tokens(table_name) if len(token) > 1
        ]
        if len(raw_tokens) > 1 and raw_tokens[0] in cls._TECHNICAL_PREFIXES:
            raw_tokens = raw_tokens[1:]
        if not raw_tokens:
            return set()

        aliases = {"".join(raw_tokens)}
        filtered_tokens = [
            token for token in raw_tokens if token not in cls._IGNORED_TABLE_TOKENS
        ]
        if filtered_tokens:
            aliases.add("".join(filtered_tokens))

        # 复合表的外键经常省略首段，例如 purchase_record_id 指向
        # package_purchase_record。只保留后缀，避免较长表的前缀抢占
        # 已存在的较短实体名，例如 package_purchase_record_equity。
        for start in range(1, len(raw_tokens) - 1):
            aliases.add("".join(raw_tokens[start:]))
        return {alias for alias in aliases if alias}

    @classmethod
    def _column_key_stems(cls, column_name: str) -> set[str]:
        """提取 user_id、order_code 等字段中的业务实体词干。"""
        tokens = cls._identifier_tokens(column_name)
        stems = {"".join(tokens)} if tokens else set()
        if tokens and tokens[-1] in cls._KEY_SUFFIXES and len(tokens) > 1:
            stems.add("".join(tokens[:-1]))
        return {stem for stem in stems if stem}

    @staticmethod
    def _type_family(raw_type: Any) -> str:
        """将不同数据库字段类型归并为连接兼容性家族。"""
        value = str(raw_type or "").lower()
        if not value:
            return "unknown"
        if any(
            token in value
            for token in ("int", "decimal", "numeric", "float", "double", "real")
        ):
            return "number"
        if any(
            token in value
            for token in ("char", "text", "string", "uuid", "binary")
        ):
            return "string"
        if any(token in value for token in ("date", "time")):
            return "datetime"
        if any(token in value for token in ("bool", "bit")):
            return "boolean"
        return "other"

    @classmethod
    def column_types_compatible(cls, left_type: Any, right_type: Any) -> bool:
        """判断两个字段是否具备基本 JOIN 类型兼容性。"""
        left_family = cls._type_family(left_type)
        right_family = cls._type_family(right_type)
        return (
            "unknown" in {left_family, right_family}
            or left_family == right_family
            or "other" in {left_family, right_family}
        )

    @staticmethod
    def _compact_table(
        raw_table: Dict[str, Any],
        fallback_name: str = "",
    ) -> Optional[Dict[str, Any]]:
        """构建关系推导专用表结构，删除枚举值、样例值和重复数据集说明。"""
        table_name = str(
            raw_table.get("table_name")
            or raw_table.get("physical_name")
            or fallback_name
            or ""
        ).strip()
        if not table_name:
            return None

        columns: List[Dict[str, Any]] = []
        for raw_column in raw_table.get("columns") or []:
            if not isinstance(raw_column, dict):
                continue
            column_name = str(
                raw_column.get("name")
                or raw_column.get("physical_name")
                or ""
            ).strip()
            if not column_name:
                continue
            column: Dict[str, Any] = {"name": column_name}
            column_type = str(raw_column.get("type") or "").strip()
            column_term = str(raw_column.get("term") or "").strip()
            column_desc = str(
                raw_column.get("desc")
                or raw_column.get("description")
                or ""
            ).strip()
            if column_type:
                column["type"] = column_type
            if column_term:
                column["term"] = column_term
            if column_desc:
                column["desc"] = column_desc
            foreign_key = str(raw_column.get("foreign_key") or "").strip()
            if foreign_key:
                column["foreign_key"] = foreign_key
            if (
                raw_column.get("pk") is True
                or raw_column.get("is_primary") in (True, 1, "1")
            ):
                column["pk"] = True
            columns.append(column)

        compact_table: Dict[str, Any] = {
            "table_name": table_name,
            "columns": columns,
        }
        table_term = str(
            raw_table.get("table_desc")
            or raw_table.get("term")
            or ""
        ).strip()
        table_desc = str(raw_table.get("description") or "").strip()
        if table_term:
            compact_table["table_desc"] = table_term
        if table_desc:
            compact_table["description"] = table_desc
        return compact_table

    @classmethod
    def parse_schema(
        cls,
        schema_context: str,
    ) -> Tuple[List[str], Dict[str, Dict[str, Any]]]:
        """解析规范 Schema 块和旧版 tables YAML，返回有序精简表索引。"""
        text = str(schema_context or "")
        table_order: List[str] = []
        table_index: Dict[str, Dict[str, Any]] = {}
        headers = list(cls._SCHEMA_HEADER_PATTERN.finditer(text))

        for index, header in enumerate(headers):
            header_attrs = header.group(1)
            if not re.search(r"\btype=table\b", header_attrs, flags=re.IGNORECASE):
                continue
            table_match = re.search(
                r"\btable=([^\s]+)",
                header_attrs,
                flags=re.IGNORECASE,
            )
            fallback_name = (
                str(table_match.group(1)).strip().strip("'\"")
                if table_match
                else ""
            )
            body_start = header.end()
            body_end = (
                headers[index + 1].start()
                if index + 1 < len(headers)
                else len(text)
            )
            try:
                raw_table = yaml.safe_load(text[body_start:body_end].strip())
            except yaml.YAMLError as exc:
                logger.warning(
                    "关系候选 Schema 块解析失败: table=%s, error=%s",
                    fallback_name or "unknown",
                    exc,
                )
                continue
            if not isinstance(raw_table, dict):
                continue
            compact = cls._compact_table(raw_table, fallback_name)
            if compact is None:
                continue
            table_name = compact["table_name"]
            if table_name not in table_index:
                table_order.append(table_name)
            table_index[table_name] = compact

        if table_index:
            logger.info(
                "关系候选规范 Schema 解析完成: table_count=%s, raw_chars=%s",
                len(table_index),
                len(text),
            )
            return table_order, table_index

        try:
            legacy_payload = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            logger.warning("关系候选旧版 Schema 解析失败: error=%s", exc)
            return [], {}
        if not isinstance(legacy_payload, dict):
            return [], {}
        for raw_table in legacy_payload.get("tables") or []:
            if not isinstance(raw_table, dict):
                continue
            compact = cls._compact_table(raw_table)
            if compact is None:
                continue
            table_name = compact["table_name"]
            if table_name not in table_index:
                table_order.append(table_name)
            table_index[table_name] = compact
        logger.info(
            "关系候选旧版 Schema 解析完成: table_count=%s, raw_chars=%s",
            len(table_index),
            len(text),
        )
        return table_order, table_index

    @classmethod
    def _score_table_pair(
        cls,
        left_table: Dict[str, Any],
        right_table: Dict[str, Any],
    ) -> Tuple[int, Tuple[str, ...], Tuple[Tuple[str, str], ...]]:
        """根据真实字段连接线索为一对表评分，不使用业务相近代替 JOIN 证据。"""
        left_columns = left_table.get("columns") or []
        right_columns = right_table.get("columns") or []
        if not left_columns or not right_columns:
            return 10, ("元数据字段不完整，交由 AI 兼容判断",), ()

        left_aliases = cls._table_aliases(left_table["table_name"])
        right_aliases = cls._table_aliases(right_table["table_name"])
        best_score = 0
        reasons: set[str] = set()
        candidate_columns: set[Tuple[str, str]] = set()

        for left_column in left_columns:
            left_name = str(left_column.get("name") or "")
            left_name_lower = left_name.lower()
            left_stems = cls._column_key_stems(left_name)
            left_is_pk = left_column.get("pk") is True
            for right_column in right_columns:
                right_name = str(right_column.get("name") or "")
                right_name_lower = right_name.lower()
                if not cls.column_types_compatible(
                    left_column.get("type"),
                    right_column.get("type"),
                ):
                    continue
                right_stems = cls._column_key_stems(right_name)
                right_is_pk = right_column.get("pk") is True

                left_foreign_key = cls._normalize_identifier(
                    left_column.get("foreign_key")
                )
                right_foreign_key = cls._normalize_identifier(
                    right_column.get("foreign_key")
                )
                right_reference = cls._normalize_identifier(
                    f"{right_table['table_name']}.{right_name}"
                )
                left_reference = cls._normalize_identifier(
                    f"{left_table['table_name']}.{left_name}"
                )
                if left_foreign_key and left_foreign_key == right_reference:
                    best_score = max(best_score, 120)
                    reasons.add(f"显式外键 {left_name} -> {right_reference}")
                    candidate_columns.add((left_name, right_name))
                if right_foreign_key and right_foreign_key == left_reference:
                    best_score = max(best_score, 120)
                    reasons.add(f"显式外键 {right_name} -> {left_reference}")
                    candidate_columns.add((left_name, right_name))

                if (
                    left_stems.intersection(right_aliases)
                    and (
                        right_is_pk
                        or right_name_lower in cls._KEY_SUFFIXES
                    )
                ):
                    best_score = max(best_score, 100)
                    reasons.add(f"{left_name} 指向表 {right_table['table_name']} 的实体键")
                    candidate_columns.add((left_name, right_name))
                if (
                    right_stems.intersection(left_aliases)
                    and (
                        left_is_pk
                        or left_name_lower in cls._KEY_SUFFIXES
                    )
                ):
                    best_score = max(best_score, 100)
                    reasons.add(f"{right_name} 指向表 {left_table['table_name']} 的实体键")
                    candidate_columns.add((left_name, right_name))

                if (
                    left_name_lower == right_name_lower
                    and left_name_lower not in cls._KEY_SUFFIXES
                    and (left_is_pk or right_is_pk)
                ):
                    best_score = max(best_score, 90)
                    reasons.add(f"同名主键候选字段 {left_name}")
                    candidate_columns.add((left_name, right_name))

                left_term = str(left_column.get("term") or "").strip().lower()
                right_term = str(right_column.get("term") or "").strip().lower()
                if left_term and left_term == right_term and (left_is_pk or right_is_pk):
                    best_score = max(best_score, 80)
                    reasons.add(f"同业务术语键字段 {left_term}")
                    candidate_columns.add((left_name, right_name))

        return (
            best_score,
            tuple(sorted(reasons)),
            tuple(sorted(candidate_columns)),
        )

    @staticmethod
    def _semantic_fragments(value: Any) -> set[str]:
        """提取可用于结构化语义匹配的中英文片段，不读取业务数据。"""
        text = str(value or "").strip().lower()
        if not text:
            return set()
        fragments = set(re.findall(r"[\u4e00-\u9fff]{2,}", text))
        fragments.update(
            token
            for token in MetadataRelationshipCandidateService._identifier_tokens(text)
            if len(token) > 1
            and token not in MetadataRelationshipCandidateService._KEY_SUFFIXES
            and token not in MetadataRelationshipCandidateService._IGNORED_TABLE_TOKENS
        )
        return fragments

    @classmethod
    def _has_semantic_overlap(cls, left: Iterable[str], right: Iterable[str]) -> bool:
        """允许完整词与带后缀的业务词匹配，例如“客户”与“客户编码”。"""
        for left_item in left:
            for right_item in right:
                if len(left_item) >= 2 and len(right_item) >= 2 and (
                    left_item in right_item or right_item in left_item
                ):
                    return True
        return False

    @classmethod
    def _smart_score_table_pair(
        cls,
        left_table: Dict[str, Any],
        right_table: Dict[str, Any],
    ) -> Tuple[int, Tuple[str, ...], Tuple[Tuple[str, str], ...]]:
        """在无主外键时按字段角色和中英文元数据语义补充低置信度候选。"""
        left_columns = left_table.get("columns") or []
        right_columns = right_table.get("columns") or []
        if not left_columns or not right_columns:
            return 0, (), ()

        left_table_context = cls._semantic_fragments(
            " ".join(
                (
                    str(left_table.get("table_name") or ""),
                    str(left_table.get("table_desc") or ""),
                    str(left_table.get("description") or ""),
                )
            )
        )
        right_table_context = cls._semantic_fragments(
            " ".join(
                (
                    str(right_table.get("table_name") or ""),
                    str(right_table.get("table_desc") or ""),
                    str(right_table.get("description") or ""),
                )
            )
        )
        left_aliases = cls._table_aliases(left_table["table_name"])
        right_aliases = cls._table_aliases(right_table["table_name"])
        best_score = 0
        reasons: set[str] = set()
        candidate_columns: set[Tuple[str, str]] = set()

        for left_column in left_columns:
            left_name = str(left_column.get("name") or "")
            left_name_lower = left_name.lower()
            left_stems = cls._column_key_stems(left_name)
            left_key_like = any(
                token in cls._SMART_KEY_SUFFIXES
                for token in cls._identifier_tokens(left_name)[-1:]
            )
            left_context = cls._semantic_fragments(
                " ".join(
                    (
                        left_name,
                        str(left_column.get("term") or ""),
                        str(left_column.get("desc") or ""),
                    )
                )
            )
            for right_column in right_columns:
                right_name = str(right_column.get("name") or "")
                right_stems = cls._column_key_stems(right_name)
                right_key_like = any(
                    token in cls._SMART_KEY_SUFFIXES
                    for token in cls._identifier_tokens(right_name)[-1:]
                )
                if not cls.column_types_compatible(
                    left_column.get("type"),
                    right_column.get("type"),
                ):
                    continue
                right_context = cls._semantic_fragments(
                    " ".join(
                        (
                            right_name,
                            str(right_column.get("term") or ""),
                            str(right_column.get("desc") or ""),
                        )
                    )
                )
                pair_score = 0
                pair_reasons: set[str] = set()
                if left_key_like and cls._has_semantic_overlap(
                    left_context, right_table_context | right_aliases
                ):
                    pair_score = max(pair_score, 58)
                    pair_reasons.add(f"{left_name} 与表 {right_table['table_name']} 语义匹配")
                if right_key_like and cls._has_semantic_overlap(
                    right_context, left_table_context | left_aliases
                ):
                    pair_score = max(pair_score, 58)
                    pair_reasons.add(f"{right_name} 与表 {left_table['table_name']} 语义匹配")
                if left_stems.intersection(right_aliases) and right_key_like:
                    pair_score = max(pair_score, 55)
                    pair_reasons.add(f"{left_name} 指向表 {right_table['table_name']} 的语义键")
                if right_stems.intersection(left_aliases) and left_key_like:
                    pair_score = max(pair_score, 55)
                    pair_reasons.add(f"{right_name} 指向表 {left_table['table_name']} 的语义键")
                if (
                    left_key_like
                    and right_key_like
                    and cls._has_semantic_overlap(left_context, right_context)
                ):
                    pair_score = max(pair_score, 48)
                    pair_reasons.add("两侧键字段业务语义匹配")
                if pair_score:
                    best_score = max(best_score, pair_score)
                    reasons.update(pair_reasons)
                    candidate_columns.add((left_name, right_name))

        return best_score, tuple(sorted(reasons)), tuple(sorted(candidate_columns))

    @classmethod
    def build_candidate_pairs_with_stats(
        cls,
        table_order: Sequence[str],
        table_index: Dict[str, Dict[str, Any]],
        *,
        include_incomplete_metadata: bool = True,
        focused_table_names: Optional[Sequence[str]] = None,
        strategy: str = "strict",
        max_candidate_pairs: Optional[int] = None,
    ) -> RelationshipCandidateBuildResult:
        """构建候选并返回智能策略的限量诊断。"""
        normalized_strategy = strategy if strategy in {"strict", "smart"} else "strict"
        candidates: List[RelationshipCandidatePair] = []
        possible_pair_count = 0
        incomplete_pair_count = 0
        for left_index, left_name in enumerate(table_order):
            left_table = table_index.get(left_name)
            if left_table is None:
                continue
            for right_name in table_order[left_index + 1:]:
                right_table = table_index.get(right_name)
                if right_table is None:
                    continue
                possible_pair_count += 1
                score, reasons, column_pairs = cls._score_table_pair(
                    left_table,
                    right_table,
                )
                if score == 10:
                    incomplete_pair_count += 1
                    if not include_incomplete_metadata:
                        continue
                if normalized_strategy == "smart" and score <= 0:
                    score, reasons, column_pairs = cls._smart_score_table_pair(
                        left_table,
                        right_table,
                    )
                if score <= 0 and any(
                    name.lower() in {left_name.lower(), right_name.lower()}
                    for name in focused_table_names or []
                ):
                    score = 5
                    reasons = ("用户自定义需求包含相关表，补充候选",)
                if score <= 0:
                    continue
                candidates.append(
                    RelationshipCandidatePair(
                        left_table=left_name,
                        right_table=right_name,
                        score=score,
                        reasons=reasons,
                        column_pairs=column_pairs,
                    )
                )

        order_positions = {
            table_name: index for index, table_name in enumerate(table_order)
        }
        if normalized_strategy == "smart":
            candidates.sort(
                key=lambda pair: (
                    -pair.score,
                    order_positions.get(pair.left_table, len(order_positions)),
                    order_positions.get(pair.right_table, len(order_positions)),
                )
            )
        else:
            candidates.sort(
                key=lambda pair: (
                    order_positions.get(pair.left_table, len(order_positions)),
                    -pair.score,
                    order_positions.get(pair.right_table, len(order_positions)),
                )
            )

        smart_candidate_pair_count = len(candidates)
        effective_limit = (
            max_candidate_pairs
            if normalized_strategy == "smart" and max_candidate_pairs is not None
            else None
        )
        truncated_pair_count = 0
        if effective_limit is not None and effective_limit >= 0:
            truncated_pair_count = max(0, len(candidates) - effective_limit)
            candidates = candidates[:effective_limit]
        logger.warning(
            "关系候选表对生成完成: strategy=%s, table_count=%s, possible_pairs=%s, "
            "candidate_pairs=%s, filtered_pairs=%s, incomplete_pairs=%s, truncated_pairs=%s",
            normalized_strategy,
            len(table_order),
            possible_pair_count,
            len(candidates),
            possible_pair_count - len(candidates),
            incomplete_pair_count,
            truncated_pair_count,
        )
        return RelationshipCandidateBuildResult(
            pairs=tuple(candidates),
            smart_candidate_pair_count=smart_candidate_pair_count,
            truncated_pair_count=truncated_pair_count,
        )

    @classmethod
    def build_candidate_pairs(
        cls,
        table_order: Sequence[str],
        table_index: Dict[str, Dict[str, Any]],
        *,
        include_incomplete_metadata: bool = True,
        focused_table_names: Optional[Sequence[str]] = None,
        strategy: str = "strict",
        max_candidate_pairs: Optional[int] = None,
    ) -> List[RelationshipCandidatePair]:
        """生成前向无重复候选表对，结果总量不设置固定上限。"""
        result = cls.build_candidate_pairs_with_stats(
            table_order,
            table_index,
            include_incomplete_metadata=include_incomplete_metadata,
            focused_table_names=focused_table_names,
            strategy=strategy,
            max_candidate_pairs=max_candidate_pairs,
        )
        return list(result.pairs)

    @classmethod
    def parse_focused_table_names(
        cls,
        user_prompt: Optional[str],
        table_order: Sequence[str],
    ) -> List[str]:
        text = str(user_prompt or "")
        if not text.strip():
            return []
        matched: List[str] = []
        for table_name in table_order:
            normalized = str(table_name or "").strip().lower()
            if normalized and re.search(
                r"(?<![a-z0-9_])" + re.escape(normalized) + r"(?![a-z0-9_])",
                text,
                flags=re.IGNORECASE,
            ):
                matched.append(table_name)
        logger.info(
            "自定义需求物理表识别完成: prompt_chars=%s, matched_tables=%s",
            len(text),
            matched,
        )
        return matched


    @staticmethod
    def group_candidate_pairs(
        candidates: Sequence[RelationshipCandidatePair],
        *,
        max_pairs_per_group: int = 8,
        max_tables_per_group: int = 12,
    ) -> List[RelationshipCandidateGroup]:
        """按调用上下文上限分组，优先保持相邻锚定表候选在同一组。"""
        groups: List[RelationshipCandidateGroup] = []
        current_pairs: List[RelationshipCandidatePair] = []
        current_tables: List[str] = []

        def flush_group() -> None:
            if not current_pairs:
                return
            groups.append(
                RelationshipCandidateGroup(
                    pairs=tuple(current_pairs),
                    table_names=tuple(current_tables),
                )
            )
            current_pairs.clear()
            current_tables.clear()

        for pair in candidates:
            pair_tables = [pair.left_table, pair.right_table]
            next_tables = list(dict.fromkeys([*current_tables, *pair_tables]))
            if current_pairs and (
                len(current_pairs) >= max_pairs_per_group
                or len(next_tables) > max_tables_per_group
            ):
                flush_group()
                next_tables = pair_tables
            current_pairs.append(pair)
            current_tables[:] = list(dict.fromkeys(next_tables))
        flush_group()
        logger.warning(
            "关系候选分组完成: candidate_pairs=%s, group_count=%s, "
            "max_pairs_per_group=%s, max_tables_per_group=%s",
            len(candidates),
            len(groups),
            max_pairs_per_group,
            max_tables_per_group,
        )
        return groups

    @staticmethod
    def render_group_schema(
        group: RelationshipCandidateGroup,
        table_index: Dict[str, Dict[str, Any]],
    ) -> str:
        """输出仅含候选键字段的紧凑 JSON，避免发送无关业务字段。"""
        relevant_columns: Dict[str, set[str]] = {
            table_name: set() for table_name in group.table_names
        }
        for pair in group.pairs:
            for left_column, right_column in pair.column_pairs:
                relevant_columns.setdefault(pair.left_table, set()).add(
                    left_column.lower()
                )
                relevant_columns.setdefault(pair.right_table, set()).add(
                    right_column.lower()
                )

        compact_tables: List[Dict[str, Any]] = []
        for table_name in group.table_names:
            table = table_index[table_name]
            selected_names = relevant_columns.get(table_name, set())
            selected_columns: List[Dict[str, Any]] = []
            for column in table.get("columns") or []:
                column_name = str(column.get("name") or "")
                column_tokens = MetadataRelationshipCandidateService._identifier_tokens(
                    column_name
                )
                is_key_like = bool(
                    column.get("pk") is True
                    or column.get("foreign_key")
                    or (
                        column_tokens
                        and column_tokens[-1]
                        in MetadataRelationshipCandidateService._KEY_SUFFIXES
                    )
                )
                if column_name.lower() in selected_names or is_key_like:
                    selected_columns.append(column)
            compact_table = {
                key: value
                for key, value in table.items()
                if key != "columns"
            }
            compact_table["columns"] = selected_columns
            compact_tables.append(compact_table)

        payload = {
            "candidate_pairs": [pair.to_prompt_dict() for pair in group.pairs],
            "tables": compact_tables,
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _normalize_identifier(value: Any) -> str:
        """去除模型可能附带的标识符引号，用于物理名称严格比较。"""
        return (
            str(value or "")
            .strip()
            .replace("`", "")
            .replace('"', "")
            .lower()
        )

    @classmethod
    def _parse_condition_operands(
        cls,
        condition: str,
    ) -> Optional[Tuple[Tuple[str, str], Tuple[str, str]]]:
        """解析简单等值 JOIN，复杂表达式不进入自动推荐结果。"""
        parts = re.split(r"\s*=\s*", str(condition or "").strip())
        if len(parts) != 2:
            return None

        operands: List[Tuple[str, str]] = []
        for part in parts:
            cleaned = part.strip().replace("`", "").replace('"', "")
            if "." not in cleaned or any(char in cleaned for char in "() +*/"):
                return None
            table_name, column_name = cleaned.rsplit(".", 1)
            table_name = cls._normalize_identifier(table_name)
            column_name = cls._normalize_identifier(column_name)
            if not table_name or not column_name:
                return None
            operands.append((table_name, column_name))
        return operands[0], operands[1]

    @classmethod
    def validate_relationship(
        cls,
        relationship: Dict[str, Any],
        group: RelationshipCandidateGroup,
        table_index: Dict[str, Dict[str, Any]],
        *,
        minimum_confidence: float = 0.70,
    ) -> Tuple[bool, str]:
        """校验模型结果是否属于候选组，并且引用真实、类型兼容的物理字段。"""
        source_table = cls._normalize_identifier(relationship.get("source_table"))
        target_table = cls._normalize_identifier(relationship.get("target_table"))
        table_lookup = {name.lower(): name for name in table_index}
        if source_table not in table_lookup or target_table not in table_lookup:
            return False, "table_not_found"
        if source_table == target_table:
            return False, "self_relationship"

        pair_key = tuple(sorted((source_table, target_table)))
        allowed_pairs = {pair.unordered_key for pair in group.pairs}
        if pair_key not in allowed_pairs:
            return False, "off_candidate_pair"

        try:
            confidence = float(relationship.get("confidence", 0) or 0)
        except (TypeError, ValueError):
            return False, "invalid_confidence"
        if confidence < minimum_confidence:
            return False, "low_confidence"
        if relationship.get("relation_type") not in cls._RELATION_TYPES:
            return False, "invalid_relation_type"

        operands = cls._parse_condition_operands(str(relationship.get("condition") or ""))
        if operands is None:
            return False, "invalid_condition"
        condition_tables = {operands[0][0], operands[1][0]}
        if condition_tables != {source_table, target_table}:
            return False, "condition_table_mismatch"

        matched_pair = next(
            (pair for pair in group.pairs if pair.unordered_key == pair_key),
            None,
        )
        if matched_pair and matched_pair.column_pairs:
            allowed_condition_keys = {
                tuple(sorted((
                    (
                        cls._normalize_identifier(matched_pair.left_table),
                        cls._normalize_identifier(left_column),
                    ),
                    (
                        cls._normalize_identifier(matched_pair.right_table),
                        cls._normalize_identifier(right_column),
                    ),
                )))
                for left_column, right_column in matched_pair.column_pairs
            }
            condition_key = tuple(sorted(operands))
            if condition_key not in allowed_condition_keys:
                return False, "off_candidate_columns"

        resolved_columns: List[Dict[str, Any]] = []
        for condition_table, condition_column in operands:
            physical_table = table_lookup.get(condition_table)
            table_schema = table_index.get(physical_table or "")
            if table_schema is None:
                return False, "condition_table_not_found"
            column_lookup = {
                str(column.get("name") or "").lower(): column
                for column in table_schema.get("columns") or []
            }
            column_schema = column_lookup.get(condition_column)
            if column_schema is None:
                return False, "condition_column_not_found"
            resolved_columns.append(column_schema)

        if not cls.column_types_compatible(
            resolved_columns[0].get("type"),
            resolved_columns[1].get("type"),
        ):
            return False, "condition_type_mismatch"
        return True, "valid"

    @staticmethod
    def count_rejection_reasons(reasons: Iterable[str]) -> Dict[str, int]:
        """汇总模型结果拒绝原因，便于运行日志诊断精度。"""
        counts: Dict[str, int] = {}
        for reason in reasons:
            counts[reason] = counts.get(reason, 0) + 1
        return counts
