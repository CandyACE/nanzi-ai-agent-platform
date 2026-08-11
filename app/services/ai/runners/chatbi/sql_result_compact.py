"""Compact large SQL tool results for model context; detect deferred incomplete replies."""

from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any

from app.services.ai.runners.chatbi.constants import (
    _SQL_RESULT_ROW_KEYS,
    SQL_RESULT_MODEL_SAMPLE_ROWS,
    SQL_RESULT_MODEL_COMPACT_THRESHOLD,
)

# 查数已成功后，模型只写了「稍后汇总」类过渡句即停轮。
_DEFERRED_SUMMARIZE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"读取完整数据后",
        r"读完完整数据后",
        r"完整数据后为您",
        r"完整数据后再",
        r"稍后.{0,12}(汇总|分析|整理|回答)",
        r"接下来.{0,16}(汇总|分析|整理|回答)",
        r"我先.{0,24}再(为您|给你)?(汇总|分析|整理)",
        r"结果较多.{0,40}(汇总|整理|分析)",
        r"待我.{0,12}(汇总|分析|整理)",
        r"等我.{0,12}(汇总|分析|整理)",
        r"我会在.{0,20}后(汇总|分析|给出)",
        r"will (summarize|analyse|analyze).{0,40}after",
        r"after (reading|loading).{0,30}(summarize|summary)",
    )
)

# 查数已有中间结果，但模型承诺「再查/再统计」却未发起新 SQL。
_DEFERRED_CONTINUE_QUERY_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"让我进一步",
        r"让我再(查|统计|按|执行|跑|获取)",
        r"让我先(查看|查一下|确认|核对|探查|检查)",
        r"我先(查看|查一下|确认|核对|探查)",
        r"先查看.{0,40}(分布|样例|编码|名称|基础信息)",
        r"我再进一步",
        r"我再(按|查|统计|执行|跑).{0,24}(统计|查询|明细|汇总)?",
        r"接下来(我)?(再|将|会)?(按|查|统计|执行|获取|细化)",
        r"我将(再|进一步).{0,24}(查|统计|执行|获取)",
        r"需要进一步.{0,24}(查|统计|查询|按)",
        r"随后.{0,16}(再查|重新查|按.{0,20}统计)",
        r"下一步.{0,16}(查|统计|执行|按)",
        r"改用.{0,20}(完整|明细).{0,16}(统计|查询)",
        r"而非.{0,40}明细.{0,20}(让我|我再|接下来)",
        r"let me (further|next|first).{0,40}(query|count|aggregate|break|check|look)",
        r"i('ll| will) (further|next|first).{0,40}(query|count|aggregate|check)",
    )
)

# 平台已有非空结果，但正文仍宣称空结果/准备探查分布（常见于自动重试后模型未见新结果）。
_CONTRADICTORY_EMPTY_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"查询返回为空",
        r"查询结果为空",
        r"返回为空",
        r"结果为空",
        r"未查询到",
        r"没有查到",
        r"查无(结果|数据|记录)",
        r"无匹配(结果|数据|记录)",
        r"暂时(没有|无).{0,12}(数据|结果)",
    )
)

# SQL 成功后正文仍只是过程句（辅助网兜；主规则看时序状态）。
_PROCESS_ONLY_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"现在(查询|查一下|查数|统计|获取)",
        r"正在(查询|查数|统计|获取|分析)",
        r"接着(查|查询|统计|分析)",
        r"下面(我)?(来)?(统计|查询|分析|看)",
        r"继续(查询|查数|分析|统计)",
        r"我来(查询|查一下|统计)",
        r"开始查询",
        r"接下来(查询|统计|分析)",
    )
)

_SUBSTANTIVE_MARKERS = (
    "| ---",
    "|---",
    "```chart",
    "```sql",
    "### ",
    "## ",
    "总数",
    "合计",
    "共 ",
    "共计",
    "条记录",
    "行数据",
)


def _is_short_deferred_candidate(text: str) -> bool:
    raw = str(text or "").strip()
    if not raw or len(raw) > 1200:
        return False
    if sum(1 for m in _SUBSTANTIVE_MARKERS if m in raw) >= 2:
        return False
    if raw.count("\n") >= 8 and ("|" in raw or "-" in raw):
        return False
    return True


def looks_like_deferred_continue_query_reply(text: str) -> bool:
    """True when reply promises another SQL/refinement round but stops."""
    raw = str(text or "").strip()
    if not _is_short_deferred_candidate(raw):
        return False
    return any(p.search(raw) for p in _DEFERRED_CONTINUE_QUERY_PATTERNS)


def looks_like_contradictory_empty_reply(text: str) -> bool:
    """True when short reply claims empty / starts probing despite cached nonempty SQL."""
    raw = str(text or "").strip()
    if not _is_short_deferred_candidate(raw):
        return False
    if any(p.search(raw) for p in _CONTRADICTORY_EMPTY_PATTERNS):
        return True
    # 「让我先查看…分布」且无实质汇总，也视为与已有成功结果冲突的半截话。
    return looks_like_deferred_continue_query_reply(raw) and (
        "空" in raw or "分布" in raw or "编码" in raw or "确认" in raw
    )


def looks_like_process_only_reply(text: str) -> bool:
    """True when short reply is only in-progress query narration, not a real answer."""
    raw = str(text or "").strip()
    if not _is_short_deferred_candidate(raw):
        return False
    return any(p.search(raw) for p in _PROCESS_ONLY_PATTERNS)


def looks_like_deferred_data_reply(text: str) -> bool:
    """True when the visible reply defers summarizing already-fetched data."""
    raw = str(text or "").strip()
    if not _is_short_deferred_candidate(raw):
        return False
    # 继续查数优先于「稍后汇总」，避免同一句被合成路径吃掉。
    if looks_like_deferred_continue_query_reply(raw):
        return False
    return any(p.search(raw) for p in _DEFERRED_SUMMARIZE_PATTERNS)


# 兼容旧名
_DEFERRED_REPLY_PATTERNS = _DEFERRED_SUMMARIZE_PATTERNS


def _extract_primary_rows(parsed: Any) -> tuple[list[Any] | None, str | None]:
    if isinstance(parsed, list):
        return parsed, None
    if not isinstance(parsed, dict):
        return None, None
    for key in _SQL_RESULT_ROW_KEYS:
        rows = parsed.get(key)
        if isinstance(rows, list):
            return rows, key
    return None, None


def _column_labels(parsed: dict[str, Any], sample_row: Any) -> list[str]:
    columns = parsed.get("columns")
    labels: list[str] = []
    if isinstance(columns, list):
        for col in columns:
            if isinstance(col, dict):
                name = str(col.get("name") or col.get("label") or "").strip()
                if name:
                    labels.append(name)
            elif col is not None:
                labels.append(str(col))
    if labels:
        return labels
    if isinstance(sample_row, dict):
        return [str(k) for k in sample_row.keys()]
    if isinstance(sample_row, (list, tuple)):
        return [f"col_{i}" for i in range(len(sample_row))]
    return []


def _cell_at(row: Any, index: int, labels: list[str]) -> Any:
    if isinstance(row, dict):
        if index < len(labels) and labels[index] in row:
            return row.get(labels[index])
        keys = list(row.keys())
        if index < len(keys):
            return row.get(keys[index])
        return None
    if isinstance(row, (list, tuple)) and index < len(row):
        return row[index]
    return None


def _build_dimension_summaries(
    rows: list[Any],
    *,
    labels: list[str],
    max_dims: int = 3,
    max_values: int = 8,
) -> list[dict[str, Any]]:
    if not rows or not labels:
        return []
    summaries: list[dict[str, Any]] = []
    for idx, label in enumerate(labels[:12]):
        values: list[str] = []
        for row in rows:
            cell = _cell_at(row, idx, labels)
            if cell is None:
                continue
            if isinstance(cell, (int, float, bool)):
                continue
            text = str(cell).strip()
            if not text or len(text) > 64:
                continue
            values.append(text)
        if len(values) < max(5, len(rows) // 5):
            continue
        unique = set(values)
        if len(unique) < 2 or len(unique) > min(40, max(8, len(rows) // 2)):
            continue
        counts = Counter(values).most_common(max_values)
        summaries.append(
            {
                "column": label,
                "distinct": len(unique),
                "top_values": [{"value": v, "count": c} for v, c in counts],
            }
        )
        if len(summaries) >= max_dims:
            break
    return summaries


def compact_sql_result_for_model(
    runner: Any,
    output: Any,
    *,
    sample_rows: int = SQL_RESULT_MODEL_SAMPLE_ROWS,
    threshold: int = SQL_RESULT_MODEL_COMPACT_THRESHOLD,
) -> str | None:
    """
    Return a compacted JSON string for large SQL results, or None if no compact needed.

    Full output must still be kept on DataRunState for follow-ups / citations / synthesis.
    """
    parsed = runner._try_parse_json_output(output)
    rows, row_key = _extract_primary_rows(parsed)
    if rows is None:
        return None
    total = len(rows)
    if total <= threshold:
        return None

    sample_n = max(1, min(int(sample_rows), total))
    if isinstance(parsed, list):
        labels = _column_labels({}, rows[0] if rows else None)
        dims = _build_dimension_summaries(rows, labels=labels)
        note = _model_context_note(total=total, sample_n=sample_n, has_dims=bool(dims))
        payload: dict[str, Any] = {
            "_model_context_note": note,
            "total_row_count": total,
            "sample_row_count": sample_n,
            "rows": rows[:sample_n],
        }
        if dims:
            payload["dimension_summaries"] = dims
        return json.dumps(payload, ensure_ascii=False)

    assert isinstance(parsed, dict)
    labels = _column_labels(parsed, rows[0] if rows else None)
    dims = _build_dimension_summaries(rows, labels=labels)
    note = _model_context_note(total=total, sample_n=sample_n, has_dims=bool(dims))
    compact: dict[str, Any] = dict(parsed)
    key = row_key or "items"
    compact[key] = rows[:sample_n]
    compact["total_row_count"] = total
    compact["sample_row_count"] = sample_n
    compact["_model_context_note"] = note
    if dims:
        compact["dimension_summaries"] = dims
    # 去掉可能很大的附属字段，避免抵消抽样收益
    for heavy in ("raw", "debug", "explain", "profile"):
        compact.pop(heavy, None)
    try:
        return json.dumps(compact, ensure_ascii=False)
    except Exception:
        return json.dumps(
            {
                "_model_context_note": note,
                "total_row_count": total,
                "sample_row_count": sample_n,
                key: rows[:sample_n],
            },
            ensure_ascii=False,
            default=str,
        )


def _model_context_note(*, total: int, sample_n: int, has_dims: bool) -> str:
    dim_part = "与维度分布摘要" if has_dims else ""
    return (
        f"结果共 {total} 行，已向模型回传前 {sample_n} 行样例{dim_part}。"
        "请基于总行数、样例与分布直接给出汇总/要点回答；"
        "禁止承诺「读取完整数据后再汇总」；"
        "禁止再用 Bash/Read/Grep 把明细重新 dump；"
        "完整明细由前端「查询结果明细」表格提供，不必在回复中逐行粘贴。\n"
        "【必须告知用户】回答开头用一两句明确说明："
        f"本次解读基于全部 {total} 行中的前 {sample_n} 行样例"
        f"{'及维度分布' if has_dims else ''}，并非对全部明细的逐行全量分析；"
        "完整明细请查看下方「查询结果明细」。"
    )


def build_model_result_scope(
    runner: Any,
    output: Any,
    *,
    sample_rows: int = SQL_RESULT_MODEL_SAMPLE_ROWS,
    threshold: int = SQL_RESULT_MODEL_COMPACT_THRESHOLD,
) -> dict[str, Any]:
    """Describe whether the model saw full rows or a sample (for UI + prompts)."""
    parsed = runner._try_parse_json_output(output)
    rows, _ = _extract_primary_rows(parsed)
    total = len(rows) if rows is not None else 0
    if total <= 0:
        return {
            "mode": "full",
            "total_row_count": 0,
            "model_row_count": 0,
            "user_notice": "",
        }
    if total <= threshold:
        return {
            "mode": "full",
            "total_row_count": total,
            "model_row_count": total,
            "user_notice": "",
        }
    sample_n = max(1, min(int(sample_rows), total))
    return {
        "mode": "sample",
        "total_row_count": total,
        "model_row_count": sample_n,
        "user_notice": (
            f"AI 解读基于全部 {total} 行中的前 {sample_n} 行样例及维度分布，"
            "并非逐行全量分析；完整明细见下方「查询结果明细」。"
        ),
    }


def mark_visible_content_emitted(state: Any) -> None:
    """Record that visible assistant text was streamed to the user."""
    state.event_seq = int(getattr(state, "event_seq", 0) or 0) + 1
    state.last_visible_content_at = state.event_seq


def mark_successful_nonempty_sql(state: Any, *, tool_name: str = "execute_sql_query") -> None:
    """Record that a nonempty business SQL result is now the latest evidence."""
    state.event_seq = int(getattr(state, "event_seq", 0) or 0) + 1
    state.last_successful_nonempty_sql_at = state.event_seq
    if tool_name:
        state.last_tool_name = str(tool_name)


def should_rescue_sql_without_followup_content(state: Any) -> bool:
    """
    Structural rescue: latest nonempty SQL happened after the last visible content.

    Covers 'process narration before SQL, then SQL succeeds, then stop' without relying on regex.
    """
    if getattr(state, "empty_sql_result", False):
        return False
    if getattr(state, "diagnostic_sql_pending_final", False):
        return False
    if getattr(state, "last_successful_sql_output", None) is None:
        return False
    if getattr(state, "sql_repeat_gate_block", False):
        return False
    if getattr(state, "deferred_continue_query", False):
        return False
    if not getattr(state, "has_successful_nonempty_sql", False):
        return False
    last_sql_at = int(getattr(state, "last_successful_nonempty_sql_at", 0) or 0)
    last_content_at = int(getattr(state, "last_visible_content_at", 0) or 0)
    if last_sql_at <= 0:
        return False
    return last_sql_at > last_content_at


def should_rescue_process_only_after_sql(state: Any) -> bool:
    """Auxiliary: content exists after SQL but is only process narration."""
    if should_rescue_sql_without_followup_content(state):
        return False
    if getattr(state, "empty_sql_result", False):
        return False
    if getattr(state, "last_successful_sql_output", None) is None:
        return False
    if getattr(state, "sql_repeat_gate_block", False):
        return False
    if getattr(state, "deferred_continue_query", False):
        return False
    if not getattr(state, "has_successful_nonempty_sql", False):
        return False
    return looks_like_process_only_reply(getattr(state, "full_content", "") or "")


def should_rescue_deferred_sql_reply(state: Any) -> bool:
    """Whether to retract a deferred summarize reply and synthesize from cached SQL."""
    if not getattr(state, "ready_to_answer", False):
        return False
    if getattr(state, "last_successful_sql_output", None) is None:
        return False
    if getattr(state, "sql_repeat_gate_block", False):
        # 已有专用缓存合成路径
        return False
    if getattr(state, "deferred_continue_query", False):
        return False
    if should_rescue_sql_without_followup_content(state):
        return False
    return looks_like_deferred_data_reply(getattr(state, "full_content", "") or "")


def should_rescue_contradictory_empty_reply(state: Any) -> bool:
    """Retract empty/probe narration when platform already cached nonempty SQL rows."""
    if getattr(state, "empty_sql_result", False):
        return False
    if getattr(state, "last_successful_sql_output", None) is None:
        return False
    if getattr(state, "sql_repeat_gate_block", False):
        return False
    if getattr(state, "deferred_continue_query", False):
        return False
    if not getattr(state, "has_successful_nonempty_sql", False):
        return False
    if should_rescue_sql_without_followup_content(state):
        return False
    return looks_like_contradictory_empty_reply(getattr(state, "full_content", "") or "")


def should_force_deferred_continue_query(state: Any) -> bool:
    """Whether to retract and force another execute_sql_query round."""
    if getattr(state, "deferred_continue_query", False):
        return True
    if not getattr(state, "ready_to_answer", False):
        return False
    if getattr(state, "last_successful_sql_output", None) is None:
        return False
    if getattr(state, "sql_repeat_gate_block", False):
        return False
    # 最新成功 SQL 后尚无正文收口 → 合成，不空转再查。
    if should_rescue_sql_without_followup_content(state):
        return False
    # 已有非空业务结果却仍说「空/先探查」→ 走缓存合成，不要再强制空转查数。
    if should_rescue_contradictory_empty_reply(state):
        return False
    if should_rescue_process_only_after_sql(state):
        return False
    return looks_like_deferred_continue_query_reply(getattr(state, "full_content", "") or "")


def mark_deferred_continue_query(state: Any) -> None:
    """Arm the deferred-continue repair kind before entering the repair loop."""
    state.deferred_continue_query = True
