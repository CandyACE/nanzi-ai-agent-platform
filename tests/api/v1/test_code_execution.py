import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import require_api_key, verify_v1_api_access
from app.main import app


pytestmark = pytest.mark.no_infrastructure


class _FakeHandle:
    execution_id = "exec-test-1"

    def __init__(self):
        self.user_id = "u-test"
        self.conversation_id = "conv-test"
        self.stopped = False

    async def events(self):
        from app.services.ai.code_execution_service import CodeExecutionEvent

        yield CodeExecutionEvent("started", {"execution_id": self.execution_id})
        yield CodeExecutionEvent(
            "output", {"stream": "stdout", "chunk": "hello\n", "sequence": 0}
        )
        yield CodeExecutionEvent(
            "finished", {"status": "succeeded", "exit_code": 0, "elapsed_ms": 1}
        )

    async def stop(self):
        if self.stopped:
            return False
        self.stopped = True
        return True


@pytest.fixture
def authenticated_api(monkeypatch):
    async def fake_require_api_key():
        return {"user_id": "u-test", "role": "user"}

    async def fake_verify_v1_api_access():
        return None

    app.dependency_overrides[require_api_key] = fake_require_api_key
    app.dependency_overrides[verify_v1_api_access] = fake_verify_v1_api_access
    yield
    app.dependency_overrides.pop(require_api_key, None)
    app.dependency_overrides.pop(verify_v1_api_access, None)


@pytest.mark.asyncio
async def test_code_execution_stream_emits_started_output_and_finished(monkeypatch, authenticated_api):
    from app.api.v1.endpoints import code_execution

    handle = _FakeHandle()
    monkeypatch.setattr(code_execution, "start_code_execution", lambda **_: handle)
    monkeypatch.setattr(code_execution, "register_execution", lambda _: None)
    monkeypatch.setattr(code_execution, "unregister_execution", lambda _: None)
    async def fake_resolve_execution_workspace(**_):
        return "/tmp"

    monkeypatch.setattr(code_execution, "resolve_execution_workspace", fake_resolve_execution_workspace)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        async with client.stream(
            "POST",
            "/api/v1/chat/code-executions/stream",
            json={"language": "python", "code": "print('hello')", "conversation_id": "conv-test"},
            headers={"X-API-Key": "test-key"},
        ) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]
            lines = [line async for line in response.aiter_lines() if line]

    body = "\n".join(lines)
    assert "event: started" in body
    assert "event: output" in body
    assert "hello\\n" in body
    assert "event: finished" in body


@pytest.mark.asyncio
async def test_code_execution_rejects_unsupported_language(authenticated_api):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/chat/code-executions/stream",
            json={"language": "javascript", "code": "console.log(1)", "conversation_id": "conv-test"},
            headers={"X-API-Key": "test-key"},
        )

    assert response.status_code == 400
    assert "暂不支持" in response.json()["message"]


@pytest.mark.asyncio
async def test_code_execution_stop_requires_matching_owner(monkeypatch, authenticated_api):
    from app.api.v1.endpoints import code_execution

    handle = _FakeHandle()
    monkeypatch.setattr(code_execution, "get_execution", lambda _execution_id: handle)
    handle.user_id = "another-user"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/chat/code-executions/exec-test-1/stop",
            json={"conversation_id": "conv-test"},
            headers={"X-API-Key": "test-key"},
        )

    assert response.status_code == 403
    assert handle.stopped is False
