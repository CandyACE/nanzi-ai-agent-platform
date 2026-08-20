import pytest

pytestmark = pytest.mark.no_infrastructure


class _FakeContext:
    user_id = 7
    conversation_id = "conv-1"
    trace_id = "trace-1"


class _FakeArtifact:
    def to_tool_payload(self):
        return {
            "filename": "note.md",
            "mime_type": "text/markdown",
            "size": 12,
            "download_url": "/api/v1/chat/generated-files/abc?token=tok",
        }


@pytest.fixture
def write_env(tmp_path, monkeypatch):
    """设置 hermetic 环境：路径映射到 tmp_path，上下文与 register_artifact 均打桩。"""
    from app.services.ai.tools import system_executive_tools

    calls = {}

    # 路径都落到 tmp_path，规避 validate_safe_path 对真实 data 前缀的依赖
    monkeypatch.setattr(
        system_executive_tools,
        "validate_safe_path",
        lambda p: str(tmp_path / p.lstrip("/\\")),
    )

    # 打桩当前会话上下文（write_file 内惰性导入 get_current_agent_context）
    monkeypatch.setattr(
        "app.core.context.get_current_agent_context",
        lambda: _FakeContext(),
    )

    async def fake_register_artifact(**kwargs):
        calls["register_artifact"] = kwargs
        return _FakeArtifact()

    # write_file 内从 generated_file_service 惰性导入 register_artifact
    monkeypatch.setattr(
        "app.services.ai.tools.generated_file_service.register_artifact",
        fake_register_artifact,
    )

    calls["tmp_path"] = tmp_path
    return calls


@pytest.mark.asyncio
async def test_write_file_without_save_artifact_skips_registry(write_env):
    from app.services.ai.tools.system_executive_tools import write_file

    result = await write_file.ainvoke({
        "path": "docs/plain.txt",
        "content": "hello",
    })

    # 默认不归口：文件落盘，但不触发 register_artifact
    assert (write_env["tmp_path"] / "docs" / "plain.txt").read_text(encoding="utf-8") == "hello"
    assert "register_artifact" not in write_env
    assert "物理写入成功" in result


@pytest.mark.asyncio
async def test_write_file_with_save_artifact_registers(write_env):
    from app.services.ai.tools.system_executive_tools import write_file

    result = await write_file.ainvoke({
        "path": "docs/note.md",
        "content": "hello world",
        "save_artifact": True,
        "artifact_type": "markdown",
    })

    assert (write_env["tmp_path"] / "docs" / "note.md").read_text(encoding="utf-8") == "hello world"
    assert "register_artifact" in write_env
    kwargs = write_env["register_artifact"]
    assert kwargs["filename"] == "note.md"
    assert kwargs["owner_user_id"] == 7
    assert kwargs["artifact_type"] == "markdown"
    assert kwargs["conversation_id"] == "conv-1"
    assert kwargs["trace_id"] == "trace-1"
    assert "/api/v1/chat/generated-files/abc?token=tok" in result