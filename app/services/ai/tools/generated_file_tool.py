"""Agent-facing tool for publishing an existing workspace file for download."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.context import get_current_agent_context
from app.services.ai.tools.generated_file_service import register_artifact
from app.services.ai.tools.tool_compat import tool

_DOCKER_WORKSPACE_ROOT = "/workspace"

_EXTENSION_ARTIFACT_TYPES = {
    ".md": "markdown",
    ".markdown": "markdown",
    ".txt": "text",
    ".csv": "csv",
    ".pdf": "pdf",
    ".docx": "word",
    ".xlsx": "excel",
    ".xlsm": "excel",
}


def _user_name(context: Any) -> str | None:
    dimensions = getattr(context, "user_dimensions", None) or {}
    raw_name = dimensions.get("user_name") or dimensions.get("username")
    if not raw_name:
        return None
    name = str(raw_name).strip()
    return name or None


def _path_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except (OSError, ValueError, RuntimeError):
        return False


def _artifact_type(path: Path, requested: str | None) -> str:
    explicit = str(requested or "").strip().lower()
    if explicit:
        return explicit
    return _EXTENSION_ARTIFACT_TYPES.get(path.suffix.lower(), "document")


async def _resolve_source_path(path: str, context: Any) -> Path:
    from app.services.ai.runtime.agentscope.workspace import (
        resolve_session_workdir,
        resolve_user_workspace_root,
        resolve_workspace_root,
    )

    raw = str(path or "").strip()
    if not raw:
        raise ValueError("发布文件时必须提供 path")
    if getattr(context, "user_id", None) is None:
        raise ValueError("当前会话缺少用户身份，无法发布下载文件")

    root = Path(await resolve_workspace_root()).resolve()
    user_root_text = resolve_user_workspace_root(
        root=str(root),
        user_id=context.user_id,
        user_name=_user_name(context),
    )
    user_root = Path(user_root_text or (root / _workspace_user_key(context))).resolve()

    raw_path = Path(raw)
    if raw == _DOCKER_WORKSPACE_ROOT or raw.startswith(f"{_DOCKER_WORKSPACE_ROOT}/"):
        candidate = user_root / raw[len(_DOCKER_WORKSPACE_ROOT):].lstrip("/\\")
    elif raw_path.is_absolute():
        candidate = raw_path
    else:
        conversation_id = getattr(context, "conversation_id", None)
        if not conversation_id:
            raise ValueError("相对路径发布需要当前会话工作目录")
        session_workdir = Path(
            resolve_session_workdir(
                root=str(root),
                user_id=context.user_id,
                user_name=_user_name(context),
                conversation_id=conversation_id,
            )
        )
        candidate = session_workdir / raw
        if not candidate.exists():
            user_candidate = user_root / raw
            if user_candidate.exists():
                candidate = user_candidate

    resolved = candidate.resolve()
    if not _path_under(resolved, user_root):
        raise ValueError("文件必须位于当前用户工作区内")
    if not resolved.is_file():
        raise ValueError("文件不存在或不可访问")
    return resolved


def _workspace_user_key(context: Any) -> str:
    from app.services.ai.runtime.agentscope.workspace import resolve_workspace_user_key

    return resolve_workspace_user_key(
        user_id=context.user_id,
        user_name=_user_name(context),
    )


@tool
async def publish_generated_file(
    path: str,
    filename: str | None = None,
    artifact_type: str | None = None,
) -> dict[str, Any]:
    """Publish an existing current-user workspace file and return its download URL.

    Call this after Write/Bash or another file-producing tool has created the
    deliverable. The returned ``download_url`` must be copied verbatim into the
    final response; never replace it with a physical path or an invented URL.
    Supports local workspace paths, session-relative paths, and Docker
    ``/workspace/...`` paths. It never creates or modifies the source file.
    """
    context = get_current_agent_context()
    if context is None:
        raise ValueError("当前会话缺少执行上下文，无法发布下载文件")

    source = await _resolve_source_path(path, context)
    display_filename = Path(str(filename or source.name)).name
    if not display_filename or display_filename in {".", ".."}:
        raise ValueError("下载文件名无效")

    try:
        artifact = await register_artifact(
            source_path=source,
            filename=display_filename,
            owner_user_id=context.user_id,
            artifact_type=_artifact_type(source, artifact_type),
            conversation_id=context.conversation_id,
            trace_id=context.trace_id,
        )
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"文件已存在，但下载地址登记失败：{exc}") from exc

    payload = artifact.to_tool_payload()
    return {
        "status": "ok",
        "summary": "已生成文件下载地址",
        "artifact_type": _artifact_type(source, artifact_type),
        "filename": payload["filename"],
        "mime_type": payload["mime_type"],
        "size": payload["size"],
        "download_url": payload["download_url"],
        "expires_at": artifact.expires_at.isoformat(),
    }
