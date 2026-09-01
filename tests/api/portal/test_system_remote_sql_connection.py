import pytest

from app.api.portal.endpoints import system


pytestmark = pytest.mark.no_infrastructure


class FakeResponse:
    status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return {"code": 200, "data": [{"ok": 1}]}


class FakeAsyncClient:
    calls = []

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, *, headers, json):
        self.calls.append({"url": url, "headers": headers, "json": json})
        return FakeResponse()


@pytest.mark.asyncio
async def test_remote_sql_connection_uses_current_form_values(monkeypatch):
    FakeAsyncClient.calls = []
    monkeypatch.setattr(system.httpx, "AsyncClient", FakeAsyncClient)

    payload = system.RagFlowConnectionTestPayload(
        external_sql_api_url=" https://sql.example.com/execute ",
        external_sql_api_key="temporary-key",
        external_sql_data_source="default_clickhouse",
        use_saved_external_sql_api_key=False,
    )

    result = await system.test_connection(
        "remote_sql", payload=payload, user={"user_id": "1"}
    )

    assert result.status == "success"
    assert FakeAsyncClient.calls == [{
        "url": "https://sql.example.com/execute",
        "headers": {"Content-Type": "application/json", "X-API-Key": "temporary-key"},
        "json": {"data_source": "default_clickhouse", "sql": "SELECT 1", "params": {}},
    }]
    assert "temporary-key" not in result.message


@pytest.mark.asyncio
async def test_remote_sql_connection_uses_saved_key_for_masked_form_value(monkeypatch):
    FakeAsyncClient.calls = []

    async def fake_get(key, *args, **kwargs):
        return {"external_sql_api_key": "saved-key"}.get(key, kwargs.get("default"))

    monkeypatch.setattr(system.ConfigService, "get", fake_get)
    monkeypatch.setattr(system.httpx, "AsyncClient", FakeAsyncClient)

    payload = system.RagFlowConnectionTestPayload(
        external_sql_api_url="https://sql.example.com/execute",
        external_sql_api_key="",
        external_sql_data_source="default_clickhouse",
        use_saved_external_sql_api_key=True,
    )

    result = await system.test_connection(
        "remote_sql", payload=payload, user={"user_id": "1"}
    )

    assert result.status == "success"
    assert FakeAsyncClient.calls[0]["headers"]["X-API-Key"] == "saved-key"


@pytest.mark.asyncio
async def test_remote_sql_connection_rejects_missing_config_without_calling_client(monkeypatch):
    class UnexpectedClient:
        def __init__(self, *args, **kwargs):
            raise AssertionError("remote SQL must not be called with incomplete config")

    monkeypatch.setattr(system.httpx, "AsyncClient", UnexpectedClient)
    payload = system.RagFlowConnectionTestPayload(
        external_sql_api_url="",
        external_sql_api_key="",
        external_sql_data_source="",
    )

    result = await system.test_connection(
        "remote_sql", payload=payload, user={"user_id": "1"}
    )

    assert result.status == "error"
    assert "配置" in result.message or "URL" in result.message


def test_system_config_keeps_common_timeouts_and_exposes_remote_sql_controls():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[3] / "frontend/src/views/SystemConfig.vue").read_text(encoding="utf-8")

    assert "data_api_timeout_seconds" in source
    assert "schema_api_timeout_seconds" in source
    assert "external_sql_api_url" in source
    assert "external_sql_api_key" in source
    assert "external_sql_data_source" in source
    assert "remoteSqlConnectionTesting" in source
    assert "testRemoteSqlConnection" in source
    assert "/api/portal/system/test-connection/remote_sql" in source
