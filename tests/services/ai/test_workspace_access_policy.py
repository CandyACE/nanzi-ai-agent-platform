import os
import stat

import pytest


pytestmark = pytest.mark.no_infrastructure


def test_current_user_workspace_is_allowed(tmp_path):
    from app.services.ai.runtime.workspace_access_policy import validate_execution_workspace

    workspace_root = tmp_path / "agent_workspaces"
    current = workspace_root / "alice__1" / "sessions" / "conv-1"
    current.mkdir(parents=True)

    resolved = validate_execution_workspace(
        current,
        workspace_root=workspace_root,
        user_info={"user_id": 1, "user_name": "alice"},
    )

    assert resolved == current.resolve()


def test_other_user_workspace_is_rejected(tmp_path):
    from app.services.ai.runtime.workspace_access_policy import (
        WorkspaceAccessDenied,
        validate_execution_workspace,
    )

    workspace_root = tmp_path / "agent_workspaces"
    other = workspace_root / "bob__2" / "sessions" / "conv-2"
    other.mkdir(parents=True)

    with pytest.raises(WorkspaceAccessDenied, match="其他用户"):
        validate_execution_workspace(
            other,
            workspace_root=workspace_root,
            user_info={"user_id": 1, "user_name": "alice"},
        )


def test_workspace_symlink_cannot_escape_current_user_root(tmp_path):
    from app.services.ai.runtime.workspace_access_policy import (
        WorkspaceAccessDenied,
        validate_execution_workspace,
    )

    workspace_root = tmp_path / "agent_workspaces"
    own_root = workspace_root / "alice__1"
    other = workspace_root / "bob__2" / "sessions" / "secret"
    other.mkdir(parents=True)
    own_root.mkdir(parents=True)
    link = own_root / "sessions"
    link.symlink_to(other, target_is_directory=True)

    with pytest.raises(WorkspaceAccessDenied, match="其他用户"):
        validate_execution_workspace(
            link / "secret",
            workspace_root=workspace_root,
            user_info={"user_id": 1, "user_name": "alice"},
        )


def test_private_workspace_directories_are_mode_700(tmp_path):
    from app.services.ai.runtime.workspace_access_policy import ensure_private_workspace_dirs

    user_root = tmp_path / "agent_workspaces" / "alice__1"
    session = user_root / "sessions" / "conv-1"
    ensure_private_workspace_dirs(user_root, session)

    assert stat.S_IMODE(os.stat(user_root).st_mode) == 0o700
    assert stat.S_IMODE(os.stat(session).st_mode) == 0o700
