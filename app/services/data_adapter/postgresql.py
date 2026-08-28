"""PostgreSQL data-source adapter and identifier helpers."""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from jinja2 import BaseLoader, Environment, Undefined
from psycopg import sql

from .base import DataSourceAdapter, SQLSafetyError, standardize_items
from .models import LogicalQuery, ResultSet


class SqlLabUndefined(Undefined):
    def __str__(self):
        return "NULL"

    def __html__(self):
        return "NULL"

    def __iter__(self):
        return iter([])

    def __bool__(self):
        return False


SQL_LAB_ENV = Environment(loader=BaseLoader(), undefined=SqlLabUndefined)
POSTGRESQL_TYPES = ("postgres", "postgresql", "pg")
logger = logging.getLogger(__name__)


def is_postgresql_type(db_type: str) -> bool:
    return str(db_type or "").strip().lower() in POSTGRESQL_TYPES


def build_postgresql_conninfo(config: Dict[str, Any]) -> Dict[str, Any]:
    """Build psycopg connection kwargs from a saved data-source config."""
    return {
        "host": config.get("host"),
        "port": int(config.get("port") or 5432),
        "dbname": config.get("database") or config.get("database_name"),
        "user": config.get("user") or config.get("db_user"),
        "password": config.get("password") or "",
        "connect_timeout": 10,
    }


def split_postgresql_identifier(name: str) -> Tuple[Optional[str], str]:
    """Split ``schema.table`` while accepting quoted identifiers."""
    parts = [part.strip().strip('"').strip("`") for part in str(name or "").split(".")]
    if len(parts) == 2 and all(parts):
        return parts[0], parts[1]
    return None, parts[-1] if parts else ""


def quote_postgresql_identifier(name: str) -> str:
    """Quote an identifier without requiring a live psycopg connection."""
    return '"' + str(name).replace('"', '""') + '"'


def qualified_identifier(name: str, default_schema: str = "public") -> sql.Composed:
    schema, table = split_postgresql_identifier(name)
    if not table:
        raise ValueError("表名不能为空")
    return sql.SQL(".").join(
        [sql.Identifier(schema or default_schema), sql.Identifier(table)]
    )


def normalize_postgresql_identifiers(sql_text: str) -> str:
    """将 SQL 中的 MySQL 反引号标识符转换为 PostgreSQL 双引号标识符。

    数据门户可能复用 MySQL 风格的物理表名（例如 ``public.ny_function``）。
    PostgreSQL 不支持反引号，因此只在 SQL 的标识符上下文中做兼容转换；
    单引号字符串、双引号标识符、注释和 dollar-quoted 字符串会原样保留。
    """
    source = str(sql_text or "")
    if "`" not in source:
        return source

    output: List[str] = []
    index = 0
    length = len(source)
    while index < length:
        current = source[index]

        # SQL 字符串中的反引号是普通文本，不能当作标识符转换。
        if current == "'":
            start = index
            index += 1
            while index < length:
                if source[index] == "'":
                    if index + 1 < length and source[index + 1] == "'":
                        index += 2
                        continue
                    index += 1
                    break
                if source[index] == "\\" and index + 1 < length:
                    index += 2
                    continue
                index += 1
            output.append(source[start:index])
            continue

        # 双引号标识符允许包含反引号，同样必须保持原样。
        if current == '"':
            start = index
            index += 1
            while index < length:
                if source[index] == '"':
                    if index + 1 < length and source[index + 1] == '"':
                        index += 2
                        continue
                    index += 1
                    break
                index += 1
            output.append(source[start:index])
            continue

        # 保留行注释和块注释内容，避免转换示例 SQL 或说明文字。
        if source.startswith("--", index):
            end = source.find("\n", index)
            if end < 0:
                output.append(source[index:])
                break
            output.append(source[index:end])
            index = end
            continue
        if source.startswith("/*", index):
            end = source.find("*/", index + 2)
            if end < 0:
                output.append(source[index:])
                break
            end += 2
            output.append(source[index:end])
            index = end
            continue

        # PostgreSQL 的 dollar-quoted 字符串常用于函数或复杂表达式。
        if current == "$":
            dollar_match = re.match(r"\$(?:[A-Za-z_][A-Za-z0-9_]*)?\$", source[index:])
            if dollar_match:
                delimiter = dollar_match.group(0)
                end = source.find(delimiter, index + len(delimiter))
                if end >= 0:
                    end += len(delimiter)
                    output.append(source[index:end])
                    index = end
                    continue

        if current != "`":
            output.append(current)
            index += 1
            continue

        # 读取一个 MySQL 反引号标识符，`` 表示标识符内部的单个反引号。
        start = index + 1
        index = start
        identifier_parts: List[str] = []
        buffer: List[str] = []
        closed = False
        while index < length:
            if source[index] == "`":
                if index + 1 < length and source[index + 1] == "`":
                    buffer.append("`")
                    index += 2
                    continue
                identifier_parts.append("".join(buffer))
                index += 1
                closed = True
                break
            buffer.append(source[index])
            index += 1

        if not closed:
            # 不完整的标识符交由数据库返回语法错误，避免猜测并改变原始 SQL。
            logger.warning("PostgreSQL SQL 存在未闭合的反引号标识符，保留原始内容")
            output.append(source[start - 1 :])
            break

        identifier = identifier_parts[0]
        # 上游把 schema.table 整体包在反引号中时，拆成 PostgreSQL 的限定标识符。
        quoted_parts = [quote_postgresql_identifier(part) for part in identifier.split(".")]
        output.append(".".join(quoted_parts))

    normalized = "".join(output)
    if normalized != source:
        logger.info("PostgreSQL SQL 已将 MySQL 反引号标识符转换为双引号")
    return normalized


class PostgreSQLAdapter(DataSourceAdapter):
    """PostgreSQL read-only adapter backed by psycopg's async connection pool."""

    def __init__(self, source_id: int):
        self.source_id = source_id

    async def execute(self, query: LogicalQuery) -> ResultSet:
        raise NotImplementedError("本地适配器仅支持执行只读物理 SQL")

    async def execute_summary(self, query: LogicalQuery, agg_fields: List[str] = None) -> Dict[str, Any]:
        raise NotImplementedError("本地适配器仅支持执行只读物理 SQL")

    async def get_tables(self) -> List[Dict[str, str]]:
        from app.services.pool_manager import DataSourcePoolManager

        pool = await DataSourcePoolManager.get_pool(self.source_id)
        query = """
            SELECT
                table_schema,
                table_name,
                COALESCE(obj_description(
                    (quote_ident(table_schema) || '.' || quote_ident(table_name))::regclass,
                    'pg_class'
                ), ''),
                table_type
            FROM information_schema.tables
            WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
              AND table_type IN ('BASE TABLE', 'VIEW')
            ORDER BY table_schema, table_name
        """
        async with pool.connection() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(query)
                rows = await cursor.fetchall()

        return [
            {
                "name": f"{row[0]}.{row[1]}",
                "comment": row[2] or "",
                "type": "view" if row[3] == "VIEW" else "table",
            }
            for row in rows
        ]

    async def get_columns(
        self,
        table_name: Optional[str] = None,
        custom_sql: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, str]]:
        from app.services.pool_manager import DataSourcePoolManager

        pool = await DataSourcePoolManager.get_pool(self.source_id)
        if custom_sql:
            raw_sql = custom_sql.strip().rstrip(";")
            try:
                raw_sql = SQL_LAB_ENV.from_string(raw_sql).render(**(params or {}))
            except Exception:
                pass
            raw_sql = normalize_postgresql_identifiers(raw_sql)
            final_sql = f"SELECT * FROM ({raw_sql}) AS _pg_columns LIMIT 0"
            async with pool.connection() as connection:
                async with connection.cursor() as cursor:
                    await cursor.execute(final_sql)
                    description = cursor.description or []
            return [{"name": desc[0], "type": str(desc[1]), "comment": ""} for desc in description]

        schema, table = split_postgresql_identifier(table_name or "")
        if not table:
            return []
        async with pool.connection() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    SELECT c.column_name, c.data_type, c.udt_name,
                           COALESCE(col_description(
                               (quote_ident(c.table_schema) || '.' || quote_ident(c.table_name))::regclass,
                               c.ordinal_position
                           ), '')
                    FROM information_schema.columns c
                    WHERE c.table_schema = %s AND c.table_name = %s
                    ORDER BY c.ordinal_position
                    """,
                    (schema or "public", table),
                )
                rows = await cursor.fetchall()
        return [
            {"name": row[0], "type": row[1] or row[2] or "String", "comment": row[3] or ""}
            for row in rows
        ]

    async def execute_sql(self, sql_text: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        from app.services.pool_manager import DataSourcePoolManager

        sql_text = normalize_postgresql_identifiers(sql_text)
        pool = await DataSourcePoolManager.get_pool(self.source_id)
        async with pool.connection() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(sql_text, params or ())
                rows = await cursor.fetchall()
                description = cursor.description or []
        return {
            "columns": [{"name": desc[0], "type": str(desc[1])} for desc in description],
            "items": standardize_items([list(row) for row in rows]),
        }

    async def preview(
        self,
        sql_text: str,
        limit: int = 100,
        params: Dict[str, Any] = None,
        offset: int = 0,
        include_total: bool = False,
    ) -> Dict[str, Any]:
        params = params or {}
        limit = min(max(int(limit or 100), 1), 1000)
        try:
            self._validate_sql_safety(sql_text)
        except SQLSafetyError as exc:
            raise ValueError(str(exc)) from exc

        rendered_sql = sql_text
        if "{{" in sql_text or "{%" in sql_text:
            try:
                rendered_sql = SQL_LAB_ENV.from_string(sql_text).render(**params)
                self._validate_sql_safety(rendered_sql)
            except SQLSafetyError as exc:
                raise ValueError(str(exc)) from exc
            except Exception as exc:
                raise ValueError(f"Jinja2 模板渲染失败: {exc}") from exc

        clean_sql = normalize_postgresql_identifiers(rendered_sql.strip().rstrip(";"))
        limit_match = re.search(r"\bLIMIT\s+(\d+)", clean_sql, re.IGNORECASE)
        if limit_match:
            final_sql = (
                clean_sql[: limit_match.start(1)]
                + str(min(int(limit_match.group(1)), limit))
                + clean_sql[limit_match.end(1) :]
            )
        else:
            final_sql = f"SELECT * FROM ({clean_sql}) AS _preview_sub LIMIT {limit}"

        from app.services.pool_manager import DataSourcePoolManager

        started = time.perf_counter()
        total_count = None
        pool = await DataSourcePoolManager.get_pool(self.source_id)
        async with pool.connection() as connection:
            async with connection.cursor() as cursor:
                if include_total and not limit_match:
                    await cursor.execute(f"SELECT COUNT(*) FROM ({clean_sql}) AS _preview_count")
                    total_count = int((await cursor.fetchone())[0])
                await cursor.execute(final_sql, params or ())
                rows = await cursor.fetchall()
                description = cursor.description or []

        result = {
            "columns": [{"name": desc[0], "type": str(desc[1])} for desc in description],
            "rows": standardize_items([list(row) for row in rows]),
            "execution_time_ms": (time.perf_counter() - started) * 1000,
            "scanned_rows": 0,
            "offset": offset,
            "limit": limit,
        }
        if total_count is not None:
            result["total_count"] = total_count
        return result
