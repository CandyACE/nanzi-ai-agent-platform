"""黄金报表结果列语义：快照构建、现取覆盖、展示标签、别名/启发式补齐。"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence


ColumnMetaPayload = Dict[str, Any]

_TOKEN_TERMS = {
    "register": "注册",
    "registration": "注册",
    "user": "用户",
    "users": "用户",
    "cust": "客户",
    "customer": "客户",
    "order": "订单",
    "orders": "订单",
    "amt": "金额",
    "amount": "金额",
    "price": "价格",
    "cost": "成本",
    "revenue": "收入",
    "sales": "销售",
    "cnt": "数量",
    "count": "数量",
    "num": "数量",
    "qty": "数量",
    "quantity": "数量",
    "total": "合计",
    "sum": "合计",
    "avg": "平均",
    "mean": "平均",
    "max": "最大",
    "min": "最小",
    "rate": "比率",
    "ratio": "比率",
    "pct": "占比",
    "percent": "占比",
    "date": "日期",
    "time": "时间",
    "datetime": "时间",
    "month": "月份",
    "year": "年份",
    "day": "日期",
    "week": "周",
    "create": "创建",
    "created": "创建",
    "update": "更新",
    "updated": "更新",
    "stat": "统计",
    "status": "状态",
    "city": "城市",
    "province": "省份",
    "region": "区域",
    "dept": "部门",
    "name": "名称",
    "id": "ID",
    "active": "活跃",
    "new": "新增",
    "old": "旧",
}

_SUFFIX_TERMS = {
    "count": "数量",
    "cnt": "数量",
    "num": "数量",
    "qty": "数量",
    "amt": "金额",
    "amount": "金额",
    "rate": "比率",
    "ratio": "比率",
    "pct": "占比",
    "date": "日期",
    "time": "时间",
    "month": "月份",
    "year": "年份",
    "name": "名称",
    "id": "ID",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _looks_chinese(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in str(text or ""))


def extract_result_column_names(parsed: Any) -> List[str]:
    """从 execute_sql 标准化结果中提取列名。"""
    if isinstance(parsed, dict):
        raw_columns = parsed.get("columns")
        if isinstance(raw_columns, list) and raw_columns:
            names: List[str] = []
            for col in raw_columns:
                if isinstance(col, dict):
                    name = str(col.get("name") or "").strip()
                else:
                    name = str(col or "").strip()
                if name:
                    names.append(name)
            if names:
                return names
        for key in ("rows", "items", "data", "records", "result"):
            rows = parsed.get(key)
            if isinstance(rows, list) and rows and isinstance(rows[0], dict):
                return [str(k) for k in rows[0].keys()]
    if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
        return [str(k) for k in parsed[0].keys()]
    return []


def extract_labels_from_result_columns(parsed: Any) -> Dict[str, str]:
    """从结果 columns 定义中提取 name->label/term。"""
    labels: Dict[str, str] = {}
    if not isinstance(parsed, dict):
        return labels
    raw_columns = parsed.get("columns")
    if not isinstance(raw_columns, list):
        return labels
    for col in raw_columns:
        if not isinstance(col, dict):
            continue
        name = str(col.get("name") or "").strip()
        if not name:
            continue
        for key in ("term", "label", "display_name", "title", "comment", "alias"):
            term = str(col.get(key) or "").strip()
            if term and (_looks_chinese(term) or key == "term"):
                labels[name] = term
                labels[name.lower()] = term
                break
    return labels


def normalize_column_meta(raw: Any) -> Optional[ColumnMetaPayload]:
    if not isinstance(raw, dict):
        return None
    columns_raw = raw.get("columns")
    if not isinstance(columns_raw, list):
        return None
    columns: List[Dict[str, Any]] = []
    for item in columns_raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        entry: Dict[str, Any] = {"name": name}
        for key in ("term", "type", "desc", "table_name"):
            value = str(item.get(key) or "").strip()
            if value:
                entry[key] = value
        # 兼容前端把 label 传来的情况
        if not entry.get("term"):
            for key in ("label", "display_name", "title"):
                value = str(item.get(key) or "").strip()
                if value:
                    entry["term"] = value
                    break
        columns.append(entry)
    if not columns:
        return None
    return {
        "version": int(raw.get("version") or 1),
        "captured_at": str(raw.get("captured_at") or _now_iso()),
        "source": str(raw.get("source") or "save_time"),
        "columns": columns,
    }


def build_column_meta_from_names(
    column_names: Sequence[str],
    *,
    term_map: Optional[Mapping[str, str]] = None,
    source: str = "save_time",
) -> Optional[ColumnMetaPayload]:
    names = [str(name).strip() for name in column_names if str(name or "").strip()]
    if not names:
        return None
    terms = term_map or {}
    columns: List[Dict[str, Any]] = []
    for name in names:
        entry: Dict[str, Any] = {"name": name}
        term = str(terms.get(name.lower()) or terms.get(name) or "").strip()
        if term:
            entry["term"] = term
        columns.append(entry)
    return {
        "version": 1,
        "captured_at": _now_iso(),
        "source": source,
        "columns": columns,
    }


def build_column_meta_from_labels(
    labels: Mapping[str, str],
    *,
    column_names: Optional[Sequence[str]] = None,
    source: str = "save_time",
) -> Optional[ColumnMetaPayload]:
    names = [str(n).strip() for n in (column_names or labels.keys()) if str(n or "").strip()]
    # 去重并保持顺序，跳过 lower 副本
    seen = set()
    ordered: List[str] = []
    for name in names:
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(name)
    if not ordered and labels:
        for key, value in labels.items():
            name = str(key).strip()
            if not name or name != name.lower() and name.lower() in labels:
                # prefer original casing keys; skip pure lower duplicates later
                pass
            if name.lower() in seen:
                continue
            if not str(value or "").strip():
                continue
            seen.add(name.lower())
            ordered.append(name)
    return build_column_meta_from_names(ordered, term_map=labels, source=source)


def merge_column_meta(
    snapshot: Any,
    live: Any,
    *,
    source: str = "execute_refresh",
) -> Optional[ColumnMetaPayload]:
    """现取覆盖同名列；快照补齐现取缺失字段。"""
    base = normalize_column_meta(snapshot) or {"version": 1, "captured_at": _now_iso(), "source": source, "columns": []}
    overlay = normalize_column_meta(live)
    by_name: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []

    def _put(entry: Dict[str, Any], *, overwrite: bool) -> None:
        name = str(entry.get("name") or "").strip()
        if not name:
            return
        key = name.lower()
        if key not in by_name:
            order.append(key)
            by_name[key] = {"name": name}
        target = by_name[key]
        if name and (overwrite or not target.get("name")):
            target["name"] = name
        for field in ("term", "type", "desc", "table_name"):
            value = str(entry.get(field) or "").strip()
            if not value:
                continue
            if overwrite or not target.get(field):
                target[field] = value

    for entry in base.get("columns") or []:
        if isinstance(entry, dict):
            _put(entry, overwrite=False)
    if overlay:
        for entry in overlay.get("columns") or []:
            if isinstance(entry, dict):
                _put(entry, overwrite=True)

    columns = [by_name[key] for key in order if key in by_name]
    if not columns:
        return None
    return {
        "version": 1,
        "captured_at": _now_iso(),
        "source": source if overlay else str(base.get("source") or source),
        "columns": columns,
    }


def column_labels_from_meta(meta: Any) -> Dict[str, str]:
    normalized = normalize_column_meta(meta)
    if not normalized:
        return {}
    labels: Dict[str, str] = {}
    for entry in normalized["columns"]:
        name = str(entry.get("name") or "").strip()
        term = str(entry.get("term") or "").strip()
        if name and term:
            labels[name] = term
            labels[name.lower()] = term
    return labels


def resolve_display_columns(
    column_names: Sequence[str],
    labels: Mapping[str, str],
) -> List[str]:
    display: List[str] = []
    for name in column_names:
        raw = str(name or "").strip()
        if not raw:
            continue
        label = str(labels.get(raw) or labels.get(raw.lower()) or "").strip()
        display.append(label or raw)
    return display


def heuristic_term_for_column(name: str) -> Optional[str]:
    """对英文物理列/别名做轻量中文启发（无把握时返回 None）。"""
    raw = str(name or "").strip()
    if not raw or _looks_chinese(raw):
        return raw if _looks_chinese(raw) else None

    # 去掉常见表前缀
    cleaned = re.sub(r"^(t_|dim_|fact_|d_|f_)", "", raw, flags=re.IGNORECASE)
    tokens = [t for t in re.split(r"[_\s]+", cleaned) if t]
    if not tokens:
        return None

    # 全小写精确词
    lower = cleaned.lower()
    if lower in _TOKEN_TERMS:
        return _TOKEN_TERMS[lower]

    parts: List[str] = []
    for token in tokens:
        key = token.lower()
        mapped = _TOKEN_TERMS.get(key) or _SUFFIX_TERMS.get(key)
        if mapped:
            parts.append(mapped)
        elif token.isalpha() and len(token) <= 3:
            # 过短无把握的英文片段跳过，避免噪声
            continue
        else:
            return None
    if not parts:
        return None
    # 去重但保序：注册+数量
    deduped: List[str] = []
    for part in parts:
        if part not in deduped:
            deduped.append(part)
    term = "".join(deduped)
    return term if _looks_chinese(term) else None


def extract_sql_alias_map(sql: Optional[str]) -> Dict[str, str]:
    """
    粗提取 SELECT 列表中的 alias -> 表达式文本。
    用于在缺少元数据时，用表达式中的物理列名反查 term。
    """
    if not sql:
        return {}
    text = str(sql)
    # 取最外层 SELECT ... FROM 之间
    match = re.search(r"select\s+(.*?)\s+from\s", text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return {}
    select_list = match.group(1)
    aliases: Dict[str, str] = {}
    # 按逗号切分，忽略函数括号内逗号的简单处理
    depth = 0
    buf: List[str] = []
    chunks: List[str] = []
    for ch in select_list:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            chunks.append("".join(buf).strip())
            buf = []
            continue
        buf.append(ch)
    if buf:
        chunks.append("".join(buf).strip())

    for chunk in chunks:
        if not chunk or chunk.strip() == "*":
            continue
        as_match = re.search(r"\bas\s+([`\"\[]?)([A-Za-z_][\w$]*)\1\s*$", chunk, flags=re.IGNORECASE)
        if as_match:
            alias = as_match.group(2)
            expr = chunk[: as_match.start()].strip()
            aliases[alias.lower()] = expr
            continue
        # expr alias（无 AS）
        tail = re.search(r"^(.*\S)\s+([A-Za-z_][\w$]*)\s*$", chunk)
        if tail and not re.search(r"[)\]]$", tail.group(1).strip()):
            # 避免把 "count(*)" 误判；要求左侧含运算符或函数痕迹
            left = tail.group(1).strip()
            alias = tail.group(2)
            if re.search(r"[\w)\]]$", left) and ("(" in left or "." in left or " " in left):
                aliases[alias.lower()] = left
    return aliases


def fill_missing_terms_with_heuristics(
    meta: Optional[ColumnMetaPayload],
    *,
    sql: Optional[str] = None,
    term_map: Optional[Mapping[str, str]] = None,
) -> Optional[ColumnMetaPayload]:
    """对仍无 term 的列：SQL 别名反查 -> 启发式中文。"""
    normalized = normalize_column_meta(meta)
    if not normalized:
        return None
    terms = dict(term_map or {})
    alias_exprs = extract_sql_alias_map(sql)
    columns: List[Dict[str, Any]] = []
    changed = False
    for entry in normalized["columns"]:
        item = dict(entry)
        name = str(item.get("name") or "").strip()
        if name and not item.get("term"):
            # 1) 别名表达式中的物理列
            expr = alias_exprs.get(name.lower()) or ""
            if expr and terms:
                physicals = re.findall(r"[A-Za-z_][\w$]*", expr)
                for physical in reversed(physicals):
                    hit = str(terms.get(physical.lower()) or "").strip()
                    if hit and _looks_chinese(hit):
                        item["term"] = hit
                        changed = True
                        break
            # 2) 启发式
            if not item.get("term"):
                guessed = heuristic_term_for_column(name)
                if guessed:
                    item["term"] = guessed
                    changed = True
        columns.append(item)
    if not changed:
        return normalized
    return {
        **normalized,
        "captured_at": _now_iso(),
        "columns": columns,
    }


async def resolve_column_meta_for_result(
    session: Any,
    *,
    parsed_result: Any,
    dataset_names: Iterable[str],
    snapshot_meta: Any = None,
    sql: Optional[str] = None,
) -> tuple[Optional[ColumnMetaPayload], Dict[str, str]]:
    """执行后解析列语义：现取覆盖快照，再补别名/启发式。"""
    from app.services.ai.federated_column_labels import (
        extract_alias_term_hints_from_join_sql,
        load_column_term_map_for_datasets,
        merge_column_term_maps,
    )

    column_names = extract_result_column_names(parsed_result)
    result_labels = extract_labels_from_result_columns(parsed_result)
    term_map = await load_column_term_map_for_datasets(session, dataset_names)
    if sql:
        term_map = merge_column_term_maps(
            term_map,
            extract_alias_term_hints_from_join_sql(sql, term_map),
        )
    term_map = merge_column_term_maps(term_map, result_labels)

    live = build_column_meta_from_names(column_names, term_map=term_map, source="execute_refresh")
    if not live and column_names:
        live = build_column_meta_from_names(column_names, source="execute_refresh")
    merged = merge_column_meta(snapshot_meta, live, source="execute_refresh")
    if not merged and column_names:
        merged = build_column_meta_from_names(column_names, source="execute_refresh")
    merged = fill_missing_terms_with_heuristics(merged, sql=sql, term_map=term_map)
    return merged, column_labels_from_meta(merged)
