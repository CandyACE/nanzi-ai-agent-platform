"""Private publication and capability-link download support for generated files."""
from __future__ import annotations

import hashlib
import hmac
import json
import mimetypes
import secrets
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.models.artifact import AiArtifact
from app.core.orm import AsyncSessionLocal
from app.utils.fs_paths import get_data_base_dir

DEFAULT_TTL = timedelta(hours=24)

_OFFICE_MIME_TYPES = {
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@dataclass(frozen=True)
class PublishedArtifact:
    artifact_id: str
    token: str
    filename: str
    mime_type: str
    size: int
    expires_at: datetime

    @property
    def download_url(self) -> str:
        return f"/api/v1/chat/generated-files/{self.artifact_id}?token={self.token}"

    def to_tool_payload(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "mime_type": self.mime_type,
            "size": self.size,
            "download_url": self.download_url,
        }


@dataclass(frozen=True)
class GeneratedFile:
    artifact_id: str
    path: Path
    filename: str
    mime_type: str
    size: int
    expires_at: datetime


def generated_files_root() -> Path:
    return Path(get_data_base_dir()) / "generated_files"


def _mime_type_for(filename: str) -> str:
    return _OFFICE_MIME_TYPES.get(Path(filename).suffix.lower()) or (
        mimetypes.guess_type(filename)[0] or "application/octet-stream"
    )


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _manifest_path(artifact_id: str) -> Path:
    return generated_files_root() / artifact_id / "manifest.json"


def _remove_artifact(artifact_id: str) -> None:
    shutil.rmtree(generated_files_root() / artifact_id, ignore_errors=True)


def _purge_expired() -> None:
    root = generated_files_root()
    if not root.is_dir():
        return
    now = datetime.now(timezone.utc)
    for artifact_dir in root.iterdir():
        manifest_path = artifact_dir / "manifest.json"
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            expires_at = datetime.fromisoformat(str(payload["expires_at"]))
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at <= now:
                shutil.rmtree(artifact_dir, ignore_errors=True)
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            shutil.rmtree(artifact_dir, ignore_errors=True)


def _path_under(path: Path, parent: Path) -> bool:
    """True when `path` is strictly inside `parent` (resolved, no symlink escape)."""
    try:
        rpath = path.resolve()
        rparent = Path(parent).resolve()
    except (OSError, ValueError, RuntimeError):
        return False
    try:
        return rpath == rparent or rparent in rpath.parents
    except (OSError, ValueError, RuntimeError):
        return False


async def _workspace_root() -> Path:
    from app.services.ai.runtime.agentscope.workspace import resolve_workspace_root

    return Path(await resolve_workspace_root())


async def register_artifact(
    *,
    source_path: str | Path,
    filename: str,
    owner_user_id: int | str | None,
    artifact_type: str,
    conversation_id: str | None = None,
    trace_id: str | None = None,
    ttl: timedelta = DEFAULT_TTL,
) -> PublishedArtifact:
    """登记一个已落在用户工作区内的产物到 ai_artifacts，不复制文件。

    与旧版同步 publish() 的区别：产物内容本身已存在于用户工作区目录，
    这里只写一条指向该文件的元信息（storage_path），由下载端点校验归属后
    直接以 FileResponse 返回原文件，避免重复占用磁盘。

    用于 Word/Excel 生成文件与导出数据（artifact_type 取 word/excel/export）。
    """
    source = Path(source_path).resolve()
    if not source.is_file():
        raise ValueError("待发布文件不存在")

    display_name = Path(filename).name
    if not display_name or display_name in {".", ".."}:
        raise ValueError("生成文件名无效")

    root = await _workspace_root()
    if not _path_under(source, root):
        raise ValueError("待发布文件必须位于用户工作区目录内")

    if owner_user_id is None:
        raise ValueError("登记工作区产物需要 owner_user_id")

    expires_at = datetime.now(timezone.utc) + ttl
    token = secrets.token_urlsafe(32)

    async with AsyncSessionLocal() as session:
        artifact = AiArtifact(
            id=uuid.uuid4().hex,
            owner_user_id=int(owner_user_id),
            conversation_id=conversation_id or None,
            trace_id=trace_id or None,
            artifact_type=artifact_type,
            filename=display_name,
            mime_type=_mime_type_for(display_name),
            size=source.stat().st_size,
            storage_path=str(source),
            token_hash=_token_hash(token),
            expires_at=expires_at,
        )
        session.add(artifact)
        await session.commit()

    return PublishedArtifact(
        artifact_id=artifact.id,
        token=token,
        filename=display_name,
        mime_type=artifact.mime_type,
        size=artifact.size,
        expires_at=expires_at,
    )


def publish(
    source_path: str | Path,
    filename: str,
    *,
    ttl: timedelta = DEFAULT_TTL,
) -> PublishedArtifact:
    source = Path(source_path).resolve()
    if not source.is_file():
        raise ValueError("待发布文件不存在")

    display_name = Path(filename).name
    if not display_name or display_name in {".", ".."}:
        raise ValueError("生成文件名无效")

    root = generated_files_root()
    root.mkdir(parents=True, exist_ok=True)
    _purge_expired()
    artifact_id = uuid.uuid4().hex
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + ttl
    artifact_dir = root / artifact_id
    artifact_dir.mkdir(mode=0o700)
    destination = artifact_dir / display_name
    shutil.copy2(source, destination)
    manifest = {
        "artifact_id": artifact_id,
        "filename": display_name,
        "mime_type": _mime_type_for(display_name),
        "size": destination.stat().st_size,
        "token_hash": _token_hash(token),
        "expires_at": expires_at.isoformat(),
    }
    (artifact_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )
    return PublishedArtifact(
        artifact_id=artifact_id,
        token=token,
        filename=display_name,
        mime_type=manifest["mime_type"],
        size=manifest["size"],
        expires_at=expires_at,
    )


def resolve_for_download(artifact_id: str, token: str) -> GeneratedFile | None:
    if len(artifact_id) != 32 or any(char not in "0123456789abcdef" for char in artifact_id):
        return None
    if not token:
        return None
    try:
        payload = json.loads(_manifest_path(artifact_id).read_text(encoding="utf-8"))
        expires_at = datetime.fromisoformat(str(payload["expires_at"]))
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            _remove_artifact(artifact_id)
            return None
        if not hmac.compare_digest(str(payload["token_hash"]), _token_hash(token)):
            return None
        filename = Path(str(payload["filename"])).name
        path = (generated_files_root() / artifact_id / filename).resolve()
        artifact_dir = (generated_files_root() / artifact_id).resolve()
        if not path.is_file() or path.parent != artifact_dir:
            return None
        return GeneratedFile(
            artifact_id=artifact_id,
            path=path,
            filename=filename,
            mime_type=str(payload["mime_type"]),
            size=int(payload["size"]),
            expires_at=expires_at,
        )
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None


async def resolve_workspace_artifact(artifact_id: str, token: str) -> GeneratedFile | None:
    """从 ai_artifacts 解析工作区产物，校验归属后返回可供 FileResponse 的实体。

    校验项：artifact_id 必须为 32 位十六进制、token 与库中 token_hash 匹配、
    未过期、storage_path 解析后位于用户工作区根之内，且文件确实存在。
    """
    if not artifact_id or len(artifact_id) != 32 or any(char not in "0123456789abcdef" for char in artifact_id):
        return None
    if not token:
        return None

    try:
        workspace_root = await _workspace_root()
    except Exception:
        return None

    async with AsyncSessionLocal() as session:
        try:
            record = await session.get(AiArtifact, artifact_id)
        except Exception:
            return None

    if record is None:
        return None

    try:
        if record.expires_at is not None:
            expires = record.expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires <= datetime.now(timezone.utc):
                return None

        if not hmac.compare_digest(record.token_hash or "", _token_hash(token)):
            return None

        storage = Path(record.storage_path).resolve()
        # 归属校验：文件必须位于用户工作区根之下，防止穿越到工作区外的任意文件。
        if not _path_under(storage, workspace_root):
            return None
        filename = Path(record.filename).name
        if not filename or not storage.is_file():
            return None

        return GeneratedFile(
            artifact_id=artifact_id,
            path=storage,
            filename=filename,
            mime_type=record.mime_type or "application/octet-stream",
            size=record.size or 0,
            expires_at=record.expires_at,
        )
    except (OSError, ValueError, TypeError):
        return None
