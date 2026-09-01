import pytest

from app.api.portal.endpoints import system


pytestmark = pytest.mark.no_infrastructure


class FakeRagFlowClient:
    instances = []
    datasets = [{"id": "dataset-1", "name": "业务知识库"}]

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.list_calls = []
        self.instances.append(self)

    async def list_datasets(self, *args, **kwargs):
        self.list_calls.append((args, kwargs))
        return list(self.datasets)


@pytest.mark.asyncio
async def test_ragflow_metadata_connection_uses_current_form_values(monkeypatch):
    FakeRagFlowClient.instances = []
    monkeypatch.setattr(system, "RagFlowClient", FakeRagFlowClient, raising=False)

    payload = system.RagFlowConnectionTestPayload(
        ragflow_api_url=" https://ragflow.example.com/ ",
        ragflow_api_key="temporary-key",
        use_saved_api_key=False,
    )

    result = await system.test_connection(
        "ragflow_metadata",
        payload=payload,
        user={"user_id": "1"},
    )

    assert result.status == "success"
    assert result.dataset_count == 1
    assert FakeRagFlowClient.instances[0].kwargs == {
        "config_prefix": "ragflow",
        "override_url": "https://ragflow.example.com",
        "override_key": "temporary-key",
    }
    assert FakeRagFlowClient.instances[0].list_calls == [
        ((), {"page": 1, "page_size": 1})
    ]
    assert "temporary-key" not in result.message
    assert "temporary-key" not in "\n".join(result.logs)


@pytest.mark.asyncio
async def test_ragflow_metadata_connection_uses_saved_key_for_masked_form_value(monkeypatch):
    FakeRagFlowClient.instances = []

    async def fake_get(key, *args, **kwargs):
        return {
            "ragflow_api_key": "saved-key",
        }.get(key, kwargs.get("default"))

    monkeypatch.setattr(system.ConfigService, "get", fake_get)
    monkeypatch.setattr(system, "RagFlowClient", FakeRagFlowClient, raising=False)

    payload = system.RagFlowConnectionTestPayload(
        ragflow_api_url="https://ragflow.example.com/",
        ragflow_api_key="",
        use_saved_api_key=True,
    )

    result = await system.test_connection(
        "ragflow_metadata",
        payload=payload,
        user={"user_id": "1"},
    )

    assert result.status == "success"
    assert FakeRagFlowClient.instances[0].kwargs["override_key"] == "saved-key"


@pytest.mark.asyncio
async def test_ragflow_metadata_connection_rejects_missing_config_without_calling_client(monkeypatch):
    class UnexpectedClient:
        def __init__(self, *args, **kwargs):
            raise AssertionError("RAGFlow must not be called with incomplete config")

    monkeypatch.setattr(system, "RagFlowClient", UnexpectedClient, raising=False)

    payload = system.RagFlowConnectionTestPayload(
        ragflow_api_url="",
        ragflow_api_key="",
        use_saved_api_key=False,
    )

    result = await system.test_connection(
        "ragflow_metadata",
        payload=payload,
        user={"user_id": "1"},
    )

    assert result.status == "error"
    assert "URL" in result.message or "API Key" in result.message


@pytest.mark.asyncio
async def test_ragflow_metadata_connection_redacts_key_from_failure_message(monkeypatch):
    class FailingClient:
        def __init__(self, *args, **kwargs):
            pass

        async def list_datasets(self, *args, **kwargs):
            raise RuntimeError("request failed for temporary-key")

    monkeypatch.setattr(system, "RagFlowClient", FailingClient, raising=False)

    payload = system.RagFlowConnectionTestPayload(
        ragflow_api_url="https://ragflow.example.com",
        ragflow_api_key="temporary-key",
        use_saved_api_key=False,
    )

    result = await system.test_connection(
        "ragflow_metadata",
        payload=payload,
        user={"user_id": "1"},
    )

    assert result.status == "error"
    assert "temporary-key" not in result.message
    assert "[REDACTED]" in result.message
