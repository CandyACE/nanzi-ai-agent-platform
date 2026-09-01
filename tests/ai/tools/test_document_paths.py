from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure


@pytest.mark.asyncio
async def test_resolve_document_input_rejects_unlisted_upload(tmp_path, monkeypatch):
    from app.services.ai.tools import document_paths

    monkeypatch.setattr(document_paths, "get_data_base_dir", lambda: str(tmp_path))
    upload = tmp_path / "uploads" / "other.xlsx"
    upload.parent.mkdir()
    upload.write_bytes(b"x")

    with pytest.raises(document_paths.DocumentPathError, match="当前会话附件"):
        await document_paths.resolve_document_input_path(
            str(upload),
            allowed_attachment_paths=[],
            user_id=7,
            conversation_id="conversation-1",
            allowed_extensions={".xlsx"},
        )


@pytest.mark.asyncio
async def test_resolve_document_input_accepts_listed_upload(tmp_path, monkeypatch):
    from app.services.ai.tools import document_paths

    monkeypatch.setattr(document_paths, "get_data_base_dir", lambda: str(tmp_path))
    upload = tmp_path / "uploads" / "report.xlsx"
    upload.parent.mkdir()
    upload.write_bytes(b"workbook")

    resolved = await document_paths.resolve_document_input_path(
        str(upload),
        allowed_attachment_paths=[str(upload)],
        user_id=7,
        conversation_id="conversation-1",
        allowed_extensions={".xlsx"},
    )

    assert resolved == Path(upload).resolve()


@pytest.mark.asyncio
async def test_resolve_document_input_accepts_file_in_current_user_workspace_uploads(
    tmp_path, monkeypatch
):
    from app.services.ai.tools import document_paths

    monkeypatch.setattr(document_paths, "get_data_base_dir", lambda: str(tmp_path))
    workspace_root = tmp_path / "agent_workspaces"

    async def resolve_workspace_root():
        return str(workspace_root)

    monkeypatch.setattr(document_paths, "resolve_workspace_root", resolve_workspace_root)
    upload = workspace_root / "admin__1" / "uploads" / "云间行_4352.docx"
    upload.parent.mkdir(parents=True)
    upload.write_bytes(b"docx")

    resolved = await document_paths.resolve_document_input_path(
        str(upload),
        allowed_attachment_paths=[],
        user_id=1,
        user_name="admin",
        conversation_id=None,
        allowed_extensions={".docx"},
    )

    assert resolved == upload.resolve()


@pytest.mark.asyncio
async def test_resolve_document_input_rejects_file_in_other_user_workspace(
    tmp_path, monkeypatch
):
    from app.services.ai.tools import document_paths

    monkeypatch.setattr(document_paths, "get_data_base_dir", lambda: str(tmp_path))
    workspace_root = tmp_path / "agent_workspaces"

    async def resolve_workspace_root():
        return str(workspace_root)

    monkeypatch.setattr(document_paths, "resolve_workspace_root", resolve_workspace_root)
    upload = workspace_root / "other__2" / "uploads" / "secret.docx"
    upload.parent.mkdir(parents=True)
    upload.write_bytes(b"docx")

    with pytest.raises(document_paths.DocumentPathError, match="当前会话缺少工作目录"):
        await document_paths.resolve_document_input_path(
            str(upload),
            allowed_attachment_paths=[],
            user_id=1,
            user_name="admin",
            conversation_id=None,
            allowed_extensions={".docx"},
        )
