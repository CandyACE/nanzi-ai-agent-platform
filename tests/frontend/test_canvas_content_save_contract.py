from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.no_infrastructure


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_canvas_shows_saved_path_and_save_action_for_unsaved_text():
    source = _source("frontend/src/components/embed/ChatCanvas.vue")

    assert "effectiveSourcePath" in source
    assert "已保存" in source
    assert "保存到目录" in source
    assert "WorkspaceDirectorySaveDialog" in source
    assert "createWorkspaceEntry" in source
    assert "content-saved" in source


def test_directory_picker_is_scoped_to_current_users_workspace():
    source = _source("frontend/src/components/embed/WorkspaceDirectorySaveDialog.vue")

    assert "/api/v1/chat/fs/list" in source
    assert "user_workspace_root" in source
    assert "is_user_workspace" in source
    assert "选择目录" in source
    assert "文件名" in source


def test_generated_filename_covers_code_html_markdown_and_text():
    source = _source("frontend/src/utils/workspaceFilePreview.ts")

    assert "buildGeneratedWorkspaceFilename" in source
    for token in (".py", ".sh", ".html", ".md", ".txt"):
        assert token in source


def test_saved_path_is_used_for_existing_file_updates():
    source = _source("frontend/src/components/embed/ChatCanvas.vue")

    assert "effectiveSourcePath.value" in source
    assert "saveWorkspaceFileContent" in source
    assert "保存失败" in source
