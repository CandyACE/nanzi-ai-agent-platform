from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api.portal.endpoints import saved_reports


pytestmark = pytest.mark.no_infrastructure


def test_normalize_saved_report_preview_payload_preserves_rows_and_infers_columns():
    payload = saved_reports._normalize_saved_report_preview_payload(
        '{"rows": [{"department": "销售", "amount": 12}], "execution_time_ms": 8}'
    )

    assert payload["columns"] == [{"name": "department"}, {"name": "amount"}]
    assert payload["rows"] == [["销售", 12]]
    assert payload["execution_time_ms"] == 8


def test_normalize_saved_report_preview_payload_unwraps_nested_data():
    payload = saved_reports._normalize_saved_report_preview_payload(
        {"data": {"columns": ["id"], "rows": [[1]]}}
    )

    assert payload["columns"] == ["id"]
    assert payload["rows"] == [[1]]


@pytest.mark.asyncio
async def test_preview_new_saved_report_sql_uses_connection_adapter_without_exposing_config():
    adapter = SimpleNamespace(
        preview=AsyncMock(return_value={"rows": [{"id": 1}], "execution_time_ms": 3})
    )

    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setattr(saved_reports, "_has_metadata_import_permission", AsyncMock(return_value=True))
        monkeypatch.setattr(
            saved_reports,
            "execute_sql_query_core",
            AsyncMock(return_value='{"allowed": true}'),
        )
        monkeypatch.setattr(
            saved_reports.DbConnectionService,
            "get_config",
            AsyncMock(return_value=SimpleNamespace(id=7, name="mysql_sales", password="must-not-leak")),
        )
        monkeypatch.setattr(
            "app.services.data_adapter.factory.get_adapter",
            AsyncMock(return_value=adapter),
        )

        response = await saved_reports.preview_new_saved_report_sql(
            saved_reports.SavedReportSqlPreviewRequest(
                sql="SELECT id FROM sales LIMIT 50",
                source_type="connection",
                connection_id=7,
            ),
            user_info={"user_id": "42", "role": "user"},
            db=AsyncMock(),
        )
    finally:
        monkeypatch.undo()

    adapter.preview.assert_awaited_once_with(
        "SELECT id FROM sales LIMIT 50",
        limit=50,
        include_total=False,
    )
    assert response.data["columns"] == [{"name": "id"}]
    assert response.data["rows"] == [[1]]
    assert "password" not in response.data


@pytest.mark.asyncio
async def test_saved_report_dataset_access_helper_rejects_inaccessible_dataset(monkeypatch):
    monkeypatch.setattr(
        saved_reports.MetadataService,
        "list_accessible_dataset_options",
        AsyncMock(return_value=[SimpleNamespace(id=9)]),
    )

    with pytest.raises(saved_reports.HTTPException) as exc_info:
        await saved_reports._ensure_saved_report_dataset_access(
            AsyncMock(),
            dataset_id=7,
            user_info={"user_id": "42", "role": "user"},
            user_id=42,
        )

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_source_options_returns_display_fields_only(monkeypatch):
    monkeypatch.setattr(saved_reports, "_has_metadata_import_permission", AsyncMock(return_value=True))
    monkeypatch.setattr(
        saved_reports.DbConnectionService,
        "list_configs",
        AsyncMock(
            return_value=[
                SimpleNamespace(
                    id=7,
                    name="mysql_sales",
                    db_type="mysql",
                    database_name="sales",
                    password="must-not-leak",
                )
            ]
        ),
    )

    response = await saved_reports.list_saved_report_source_options(
        user_info={"user_id": "42", "role": "user"},
        db=AsyncMock(),
    )

    assert response.data == [
        {
            "id": 7,
            "name": "mysql_sales",
            "source_key": "mysql_sales",
            "db_type": "mysql",
            "database_name": "sales",
        }
    ]


@pytest.mark.asyncio
async def test_dataset_preview_rechecks_sql_access_before_query(monkeypatch):
    dataset = SimpleNamespace(id=3, name="sales", data_source="clickhouse")
    execute = AsyncMock(
        side_effect=[
            '{"allowed": true}',
            '{"columns": ["id"], "rows": [[1]]}',
        ]
    )
    monkeypatch.setattr(
        saved_reports.MetadataService,
        "list_accessible_dataset_options",
        AsyncMock(return_value=[dataset]),
    )
    monkeypatch.setattr(saved_reports, "execute_sql_query_core", execute)

    response = await saved_reports.preview_new_saved_report_sql(
        saved_reports.SavedReportSqlPreviewRequest(
            sql="SELECT id FROM sales",
            source_type="dataset",
            dataset_id=3,
        ),
        user_info={"user_id": "42", "role": "user"},
        db=AsyncMock(),
    )

    assert response.data["rows"] == [[1]]
    assert execute.await_count == 2
    assert execute.await_args_list[0].kwargs["auth_check_only"] is True
    assert execute.await_args_list[1].kwargs["auth_check_only"] is False


@pytest.mark.asyncio
async def test_connection_preview_does_not_execute_when_permission_precheck_fails(monkeypatch):
    adapter = SimpleNamespace(preview=AsyncMock())
    monkeypatch.setattr(saved_reports, "_has_metadata_import_permission", AsyncMock(return_value=True))
    monkeypatch.setattr(
        saved_reports.DbConnectionService,
        "get_config",
        AsyncMock(return_value=SimpleNamespace(id=7, name="mysql_sales")),
    )
    monkeypatch.setattr(
        saved_reports,
        "_precheck_saved_report_sql_access",
        AsyncMock(side_effect=saved_reports.HTTPException(status_code=403, detail="表无权限")),
    )
    monkeypatch.setattr(
        "app.services.data_adapter.factory.get_adapter",
        AsyncMock(return_value=adapter),
    )

    with pytest.raises(saved_reports.HTTPException) as exc_info:
        await saved_reports.preview_new_saved_report_sql(
            saved_reports.SavedReportSqlPreviewRequest(
                sql="SELECT secret_amount FROM secret_sales",
                source_type="connection",
                connection_id=7,
            ),
            user_info={"user_id": "42", "role": "user"},
            db=AsyncMock(),
        )

    assert exc_info.value.status_code == 403
    adapter.preview.assert_not_awaited()
