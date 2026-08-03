"""Directory-level access policy for per-user AgentScope workspaces."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

class WorkspaceAccessDenied(PermissionError):
    """Raised when an execution workspace escapes the current user's root."""


def user_workspace_root(workspace_root: str | os.PathLike[str], user_info: dict[str, Any]) -> Path:
    from app.services.ai.runtime.agentscope.workspace import (
        extract_workspace_identity,
        resolve_workspace_user_key,
    )

    user_id, user_name = extract_workspace_identity(user_info=user_info)
    if user_id is None:
        raise WorkspaceAccessDenied("无法解析当前用户，拒绝访问用户工作区。")
    user_key = resolve_workspace_user_key(user_id=user_id, user_name=user_name)
    return Path(workspace_root).expanduser().resolve() / user_key


def _is_within(root: Path, target: Path) -> bool:
    try:
        target.relative_to(root)
        return True
    except ValueError:
        return False


def validate_execution_workspace(
    workspace: str | os.PathLike[str],
    *,
    workspace_root: str | os.PathLike[str],
    user_info: dict[str, Any],
) -> Path:
    """Resolve and validate an execution cwd against the current user's root.

    ``resolve()`` makes ``..`` and symlink escapes visible before the boundary
    check. This protects the server-selected execution directory; arbitrary
    paths opened by code still require an OS/container sandbox for full
    isolation.
    """
    private_root = user_workspace_root(workspace_root, user_info)
    target = Path(workspace).expanduser().resolve(strict=False)
    if not _is_within(private_root, target):
        raise WorkspaceAccessDenied(
            "安全越权拦截：代码执行目录不能离开当前用户工作区，禁止访问其他用户目录。"
        )
    return target


def ensure_private_workspace_dirs(
    user_root: str | os.PathLike[str],
    session_dir: str | os.PathLike[str],
) -> None:
    """Create private workspace directories with owner-only permissions."""
    root = Path(user_root).expanduser().resolve()
    session = Path(session_dir).expanduser().resolve(strict=False)
    if not _is_within(root, session):
        raise WorkspaceAccessDenied("会话目录必须位于当前用户工作区内。")

    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(root, 0o700)
    session.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(session, 0o700)
