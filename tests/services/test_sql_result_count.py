"""ChatBI SQL exact-count contract tests."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.services.sql_query_execution_service as sql_service
from app.services.ai.tools.data_api import call_external_sql_api


pytestmark = pytest.mark.no_infrastructure


def test_build_count_sql_removes_top_level_limit_and_order_for_mysql():
    sql = "SELECT * FROM t WHERE event_date = '2025-11-01' ORDER BY id LIMIT 1000"

    count_sql = sql_service.build_unbounded_count_sql(sql, dialect="mysql")

    assert count_sql == (
        "SELECT COUNT(*) FROM "
        "(SELECT * FROM t WHERE event_date = '2025-11-01') AS _count_query"
    )


def test_build_count_sql_uses_oracle_alias_syntax():
    sql = "SELECT * FROM t FETCH FIRST 1000 ROWS ONLY"

    count_sql = sql_service.build_unbounded_count_sql(sql, dialect="oracle")

    assert "COUNT(*)" in count_sql.upper()
    assert "FETCH FIRST" not in count_sql.upper()
    assert " AS _COUNT_QUERY" not in count_sql.upper()


@pytest.mark.asyncio
async def test_local_sql_result_contains_exact_total_and_returned_count():
    adapter = MagicMock()
    adapter.execute_sql = AsyncMock(
        side_effect=[
            {"columns": [{"name": "_total_count"}], "items": [[238]]},
            {"columns": [{"name": "id"}], "items": [[1], [2]]},
        ]
    )

    async def config_get(key, default=None):
        return {"data_api_timeout_seconds": "60"}.get(key, default)

    with patch.dict("os.environ", {"SQL_EXECUTION_MODE": "local"}), \
         patch("app.services.data_adapter.factory.get_adapter", return_value=adapter), \
         patch("app.services.config_service.ConfigService.get", side_effect=config_get), \
         patch("app.core.redis.get_redis", return_value=None):
        result = await call_external_sql_api(
            "SELECT * FROM t WHERE event_date = '2025-11-01' LIMIT 1000",
            data_source="mysql_test",
            include_total=True,
        )

    payload = json.loads(result)
    assert payload["total_count"] == 238
    assert payload["returned_count"] == 2
    assert payload["truncated"] is True
    assert payload["count_status"] == "exact"
    executed_count_sql = adapter.execute_sql.await_args_list[0].args[0]
    executed_detail_sql = adapter.execute_sql.await_args_list[1].args[0]
    assert "COUNT(*)" in executed_count_sql.upper()
    assert "LIMIT 1000" not in executed_count_sql.upper()
    assert "LIMIT 1000" in executed_detail_sql.upper()


@pytest.mark.asyncio
async def test_count_failure_keeps_detail_rows_without_claiming_exact_total():
    adapter = MagicMock()
    adapter.execute_sql = AsyncMock(
        side_effect=[
            RuntimeError("count unavailable"),
            {"columns": [{"name": "id"}], "items": [[1], [2]]},
        ]
    )

    async def config_get(key, default=None):
        return {"data_api_timeout_seconds": "60"}.get(key, default)

    with patch.dict("os.environ", {"SQL_EXECUTION_MODE": "local"}), \
         patch("app.services.data_adapter.factory.get_adapter", return_value=adapter), \
         patch("app.services.config_service.ConfigService.get", side_effect=config_get), \
         patch("app.core.redis.get_redis", return_value=None):
        result = await call_external_sql_api(
            "SELECT * FROM t WHERE event_date = '2025-11-01' LIMIT 1000",
            data_source="mysql_test",
            include_total=True,
        )

    payload = json.loads(result)
    assert payload["total_count"] is None
    assert payload["returned_count"] == 2
    assert payload["truncated"] is None
    assert payload["count_status"] == "unknown"


@pytest.mark.asyncio
async def test_local_postgresql_execution_normalizes_legacy_metric_functions():
    """验证统一 SQL 执行入口会在调用 PostgreSQL 适配器前转换历史指标函数。"""
    adapter = MagicMock()
    adapter.execute_sql = AsyncMock(
        return_value={"columns": [{"name": "created_day"}], "items": [["2026-08-28"]]}
    )

    async def config_get(key, default=None):
        return {"data_api_timeout_seconds": "60"}.get(key, default)

    with patch.dict("os.environ", {"SQL_EXECUTION_MODE": "local"}), \
         patch("app.services.data_adapter.factory.get_adapter", return_value=adapter), \
         patch("app.services.config_service.ConfigService.get", side_effect=config_get), \
         patch("app.core.redis.get_redis", return_value=None):
        result = await call_external_sql_api(
            "SELECT toDate(parseDateTimeBestEffort(create_time)) AS created_day FROM orders",
            data_source="postgresql_demo",
        )

    assert "created_day" in result
    executed_sql = adapter.execute_sql.await_args.args[0]
    assert "parseDateTimeBestEffort" not in executed_sql
    assert "toDate(" not in executed_sql
    assert "CAST(CAST(create_time AS TIMESTAMP) AS DATE)" in executed_sql


@pytest.mark.asyncio
async def test_remote_sql_result_contains_exact_total_and_keeps_detail_limit():
    count_response = MagicMock(is_error=False)
    count_response.json.return_value = {
        "code": 200,
        "data": {"columns": [{"name": "count"}], "items": [[238]]},
    }
    detail_response = MagicMock(is_error=False)
    detail_response.json.return_value = {
        "code": 200,
        "data": {"columns": [{"name": "id"}], "items": [[1], [2]]},
    }
    client = MagicMock()
    client.post = AsyncMock(side_effect=[count_response, detail_response])

    async def config_get(key, default=None):
        return {
            "external_sql_api_url": "http://remote/sql",
            "external_sql_api_key": "test-key",
            "data_api_timeout_seconds": "60",
        }.get(key, default)

    with patch.dict("os.environ", {"SQL_EXECUTION_MODE": "remote"}), \
         patch("app.services.config_service.ConfigService.get", side_effect=config_get), \
         patch("app.core.http_client.GlobalHttpClient.get_client", return_value=client), \
         patch("app.core.redis.get_redis", return_value=None):
        result = await call_external_sql_api(
            "SELECT * FROM t WHERE event_date = '2025-11-01' LIMIT 1000",
            data_source="mysql_test",
            include_total=True,
        )

    payload = json.loads(result)
    assert payload["total_count"] == 238
    assert payload["returned_count"] == 2
    assert payload["count_status"] == "exact"
    assert client.post.await_count == 2
    assert "COUNT(*)" in client.post.await_args_list[0].kwargs["json"]["sql"].upper()
    assert "LIMIT 1000" not in client.post.await_args_list[0].kwargs["json"]["sql"].upper()
    assert "LIMIT 1000" in client.post.await_args_list[1].kwargs["json"]["sql"].upper()
