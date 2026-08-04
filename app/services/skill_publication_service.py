"""Personal skill publication snapshots and platform materialization."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import desc, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.permission import ResourcePermission, UserRoleRelation
from app.models.skill_publication import SkillPublication, SkillPublicationVersion
from app.models.user import User
from app.services.ai.skill_resolver import get_user_personal_skills_dir
from app.services.portal_notification_service import PortalNotificationService
from app.utils.skill_metadata import parse_skill_frontmatter


MAX_FILE_SIZE = 20 * 1024 * 1024
MAX_SNAPSHOT_SIZE = 20 * 1024 * 1024
_SKILL_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


@dataclass(frozen=True)
class SnapshotStats:
    content_sha256: str
    file_count: int
    total_size: int


@dataclass(frozen=True)
class SnapshotInfo(SnapshotStats):
    snapshot_path: str
    source_path: str
    publication_id: str
    version_number: int


@dataclass(frozen=True)
class MaterializeResult:
    materialized_path: str
    content_sha256: str
    file_count: int
    total_size: int


class PublicationNotFoundError(LookupError):
    pass


class PublicationConflictError(RuntimeError):
    pass


def publication_snapshot_root() -> str:
    """Return the durable snapshot root beside the configured platform skills root."""

    root = os.path.join(os.path.dirname(os.path.abspath(settings.SKILLS_DIR)), "skill_publication_snapshots")
    os.makedirs(root, mode=0o700, exist_ok=True)
    return root


def _validate_skill_id(skill_id: str) -> None:
    if not skill_id or not _SKILL_ID_RE.fullmatch(skill_id):
        raise ValueError("invalid skill id")


def _assert_inside(root: str, path: str) -> None:
    if os.path.commonpath([os.path.abspath(root), os.path.abspath(path)]) != os.path.abspath(root):
        raise ValueError("skill path escapes root")


def _walk_files(root: str):
    root_path = Path(root).resolve()
    if not root_path.is_dir():
        raise ValueError("skill snapshot root does not exist")

    for current, dirnames, filenames in os.walk(root_path, followlinks=False):
        current_path = Path(current)
        dirnames[:] = sorted(dirnames)
        filenames[:] = sorted(filenames)
        for name in [*dirnames, *filenames]:
            if name.startswith("."):
                raise ValueError("hidden files are not publishable")
            path = current_path / name
            if path.is_symlink():
                raise ValueError("symlink files are not publishable")
            _assert_inside(str(root_path), str(path))
        for name in filenames:
            yield current_path / name


def validate_snapshot_tree(root: str) -> SnapshotStats:
    """Validate a skill tree and calculate a deterministic content fingerprint."""

    root_path = Path(root).resolve()
    skill_md = root_path / "SKILL.md"
    if not skill_md.is_file() or skill_md.is_symlink():
        raise ValueError("SKILL.md is required")

    hasher = hashlib.sha256()
    file_count = 0
    total_size = 0
    files = sorted(_walk_files(str(root_path)), key=lambda path: path.relative_to(root_path).as_posix())
    for path in files:
        size = path.stat().st_size
        if size > MAX_FILE_SIZE:
            raise ValueError("skill file exceeds 20MB")
        total_size += size
        if total_size > MAX_SNAPSHOT_SIZE:
            raise ValueError("skill snapshot exceeds 20MB")
        relative = path.relative_to(root_path).as_posix().encode("utf-8")
        hasher.update(relative)
        hasher.update(b"\0")
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(chunk)
        file_count += 1
    return SnapshotStats(hasher.hexdigest(), file_count, total_size)


def _copy_tree_contents(source: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for entry in sorted(source.iterdir(), key=lambda item: item.name):
        destination = target / entry.name
        if entry.is_symlink():
            raise ValueError("symlink files are not publishable")
        if entry.is_dir():
            shutil.copytree(entry, destination, symlinks=False)
        else:
            shutil.copy2(entry, destination)


def create_personal_skill_snapshot(
    *,
    user: dict[str, Any],
    skill_id: str,
    publication_id: str,
    version_number: int,
) -> SnapshotInfo:
    """Copy the current personal skill into an immutable, validated snapshot."""

    _validate_skill_id(skill_id)
    if not publication_id or int(version_number) < 1:
        raise ValueError("invalid publication version")
    personal_root = get_user_personal_skills_dir(user)
    if not personal_root:
        raise ValueError("user workspace is unavailable")
    source_path = os.path.abspath(os.path.join(personal_root, skill_id))
    _assert_inside(personal_root, source_path)
    if not os.path.isdir(source_path):
        raise FileNotFoundError("personal skill does not exist")
    stats = validate_snapshot_tree(source_path)

    publication_root = Path(publication_snapshot_root()) / publication_id
    publication_root.mkdir(parents=True, exist_ok=True)
    destination = publication_root / f"v{int(version_number)}"
    if destination.exists():
        raise FileExistsError("publication snapshot already exists")
    temporary = Path(tempfile.mkdtemp(prefix=f".v{int(version_number)}-", dir=str(publication_root)))
    try:
        _copy_tree_contents(Path(source_path), temporary)
        copied_stats = validate_snapshot_tree(str(temporary))
        if copied_stats != stats:
            raise ValueError("snapshot changed while copying")
        os.replace(str(temporary), str(destination))
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return SnapshotInfo(
        snapshot_path=str(destination),
        source_path=source_path,
        publication_id=publication_id,
        version_number=int(version_number),
        content_sha256=stats.content_sha256,
        file_count=stats.file_count,
        total_size=stats.total_size,
    )


def _validate_platform_skill_id(platform_skill_id: str) -> None:
    _validate_skill_id(platform_skill_id)


def _write_platform_metadata(
    skill_dir: Path,
    *,
    platform_skill_id: str,
    version_number: int,
    publication_id: str | None = None,
) -> None:
    skill_md = skill_dir / "SKILL.md"
    content = skill_md.read_text(encoding="utf-8")
    metadata = [
        f"platform_skill_id: {platform_skill_id}",
        f"publication_version: {int(version_number)}",
    ]
    if publication_id:
        metadata.append(f"publication_id: {publication_id}")
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if match:
        frontmatter = [
            line
            for line in match.group(1).splitlines()
            if not line.lower().startswith(("platform_skill_id:", "publication_version:", "publication_id:"))
        ]
        frontmatter_text = "\n".join([*frontmatter, *metadata])
        replacement = f"---\n{frontmatter_text}\n---\n"
        skill_md.write_text(replacement + content[match.end():], encoding="utf-8")
    else:
        metadata_text = "\n".join(metadata)
        skill_md.write_text(f"---\n{metadata_text}\n---\n\n{content}", encoding="utf-8")


def materialize_snapshot(
    *,
    snapshot_path: str,
    platform_skill_id: str,
    version_number: int,
    publication_id: str | None = None,
) -> MaterializeResult:
    """Atomically replace the active platform directory with a snapshot."""

    _validate_platform_skill_id(platform_skill_id)
    stats = validate_snapshot_tree(snapshot_path)
    skills_root = Path(os.path.abspath(settings.SKILLS_DIR))
    skills_root.mkdir(parents=True, exist_ok=True)
    target = skills_root / platform_skill_id
    staged = Path(tempfile.mkdtemp(prefix=f".{platform_skill_id}-", dir=str(skills_root)))
    backup: Path | None = None
    try:
        _copy_tree_contents(Path(snapshot_path), staged)
        copied_stats = validate_snapshot_tree(str(staged))
        if copied_stats != stats:
            raise ValueError("materialized skill changed while copying")
        if target.exists():
            backup = skills_root / f".{platform_skill_id}.backup-{uuid.uuid4().hex}"
            os.replace(str(target), str(backup))
        os.replace(str(staged), str(target))
        _write_platform_metadata(
            target,
            platform_skill_id=platform_skill_id,
            version_number=version_number,
            publication_id=publication_id,
        )
        if backup is not None:
            shutil.rmtree(backup, ignore_errors=True)
    except Exception:
        shutil.rmtree(staged, ignore_errors=True)
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
        if backup is not None and backup.exists():
            os.replace(str(backup), str(target))
        raise
    return MaterializeResult(
        materialized_path=str(target),
        content_sha256=stats.content_sha256,
        file_count=stats.file_count,
        total_size=stats.total_size,
    )


def _user_id(user: dict[str, Any]) -> int:
    try:
        return int(user.get("user_id") or user.get("id"))
    except (TypeError, ValueError):
        raise ValueError("invalid user id")


def _meta_for_personal_skill(*, user: dict[str, Any], skill_id: str) -> dict[str, str]:
    personal_root = get_user_personal_skills_dir(user)
    if not personal_root:
        raise ValueError("user workspace is unavailable")
    skill_dir = os.path.join(personal_root, skill_id)
    if not os.path.isdir(skill_dir) or not os.path.isfile(os.path.join(skill_dir, "SKILL.md")):
        raise FileNotFoundError("personal skill does not exist or is missing SKILL.md")
    return parse_skill_frontmatter(skill_id, os.path.join(skill_dir, "SKILL.md"))


def _platform_skill_id(name: str, publication_id: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.lower()).strip("-") or "skill"
    return f"public-{slug[:80]}-{publication_id.replace('-', '')[:8]}"


def _publication_payload(publication: SkillPublication, version: SkillPublicationVersion | None) -> dict[str, Any]:
    effective_status = publication.status
    if version is not None and version.status in {"REJECTED", "WITHDRAWN"}:
        effective_status = version.status
    return {
        "publication_id": publication.id,
        "version_id": version.id if version else None,
        "skill_id": publication.source_personal_skill_id,
        "platform_skill_id": publication.platform_skill_id,
        "name": publication.name,
        "description": publication.description or "",
        "publication_status": effective_status,
        "version_number": version.version_number if version else publication.current_version,
        "version_status": version.status if version else None,
        "current_public_version": publication.current_version,
        "pending_version": version.version_number if version and version.status == "PENDING" else None,
        "last_review_comment": version.review_comment if version else None,
        "content_sha256": version.content_sha256 if version else None,
        "withdrawn_by": version.withdrawn_by if version else None,
        "withdrawn_at": version.withdrawn_at.isoformat() if version and version.withdrawn_at else None,
    }


async def _versions_for_publication(session: AsyncSession, publication_id: str) -> list[SkillPublicationVersion]:
    result = await session.execute(
        select(SkillPublicationVersion)
        .where(SkillPublicationVersion.publication_id == publication_id)
        .order_by(desc(SkillPublicationVersion.version_number))
    )
    return list(result.scalars().all())


async def _skill_publication_reviewer_ids(session: AsyncSession) -> list[int]:
    direct_reviewer_ids = select(ResourcePermission.user_id).where(
        ResourcePermission.resource_type == "element",
        ResourcePermission.resource_id == "element:skills:admin",
        ResourcePermission.enabled.is_(True),
        ResourcePermission.user_id.is_not(None),
    )
    role_reviewer_ids = (
        select(UserRoleRelation.user_id)
        .join(ResourcePermission, ResourcePermission.role_id == UserRoleRelation.role_id)
        .where(
            ResourcePermission.resource_type == "element",
            ResourcePermission.resource_id == "element:skills:admin",
            ResourcePermission.enabled.is_(True),
        )
    )
    result = await session.execute(
        select(User.id)
        .where(
            User.status == 1,
            or_(
                User.role == "admin",
                User.id.in_(direct_reviewer_ids),
                User.id.in_(role_reviewer_ids),
            ),
        )
        .order_by(User.id.asc())
    )
    return [int(user_id) for user_id in result.scalars().all()]


async def notify_skill_publication_reviewers(
    session: AsyncSession,
    *,
    publication: SkillPublication,
    version: SkillPublicationVersion,
    submitted_by: dict[str, Any],
) -> None:
    reviewer_ids = await _skill_publication_reviewer_ids(session)
    submitter_name = str(
        submitted_by.get("real_name")
        or submitted_by.get("user_name")
        or submitted_by.get("user_id")
        or "用户"
    )
    for reviewer_id in reviewer_ids:
        await PortalNotificationService.create(
            session,
            user_id=reviewer_id,
            title=f"技能发布待审核：{publication.name}",
            content=(
                f"用户 {submitter_name} 提交了个人技能「{publication.name}」"
                f" v{version.version_number}，请前往技能工作台的“待审核”Tab 处理。"
            ),
            level="info",
            category="skill_publication",
            resource_type="skill_publication",
            resource_id=version.id,
            metadata={
                "action": "open_skill_publication_review",
                "publication_id": publication.id,
                "version_id": version.id,
                "version_number": version.version_number,
            },
        )


async def withdraw_personal_skill_publication(
    session: AsyncSession,
    *,
    user: dict[str, Any],
    skill_id: str,
) -> dict[str, Any]:
    """Withdraw the current user's pending publication without deleting its audit record."""

    user_id = _user_id(user)
    result = await session.execute(
        select(SkillPublicationVersion, SkillPublication)
        .join(SkillPublication, SkillPublication.id == SkillPublicationVersion.publication_id)
        .where(
            SkillPublication.source_user_id == user_id,
            SkillPublication.source_personal_skill_id == skill_id,
        )
        .order_by(desc(SkillPublicationVersion.version_number))
    )
    row = result.first()
    if not row:
        raise PublicationNotFoundError("publication not found")
    version, publication = row
    if version.status != "PENDING":
        raise PublicationConflictError("publication version is no longer pending")

    version.status = "WITHDRAWN"
    version.withdrawn_by = user_id
    version.withdrawn_at = datetime.now()
    if publication.current_version is None:
        publication.status = "UNPUBLISHED"
    else:
        publication.status = "PUBLISHED"
    publication.updated_at = datetime.now()
    await session.flush()
    return _publication_payload(publication, version)


async def submit_personal_skill(session: AsyncSession, *, user: dict[str, Any], skill_id: str) -> dict[str, Any]:
    """Create a pending immutable snapshot for the current user's personal skill."""

    user_id = _user_id(user)
    meta = _meta_for_personal_skill(user=user, skill_id=skill_id)
    publication_result = await session.execute(
        select(SkillPublication)
        .where(
            SkillPublication.source_user_id == user_id,
            SkillPublication.source_personal_skill_id == skill_id,
        )
        .order_by(desc(SkillPublication.updated_at))
    )
    publication = publication_result.scalars().first()
    if publication is None:
        publication = SkillPublication(
            id=str(uuid.uuid4()),
            source_user_id=user_id,
            source_personal_skill_id=skill_id,
            name=meta.get("name") or skill_id,
            description=meta.get("description") or "",
            status="PENDING",
        )
        session.add(publication)
        await session.flush()
    else:
        publication.name = meta.get("name") or publication.name or skill_id
        publication.description = meta.get("description") or publication.description or ""

    versions = await _versions_for_publication(session, publication.id)
    pending = next((version for version in versions if version.status == "PENDING"), None)
    source_root = get_user_personal_skills_dir(user)
    if not source_root:
        raise ValueError("user workspace is unavailable")
    source_stats = validate_snapshot_tree(os.path.join(source_root, skill_id))
    if pending is not None:
        if pending.content_sha256 == source_stats.content_sha256:
            return _publication_payload(publication, pending)
        raise PublicationConflictError("a different publication version is already pending")

    next_version = (max((version.version_number for version in versions), default=0) + 1)
    snapshot = create_personal_skill_snapshot(
        user=user,
        skill_id=skill_id,
        publication_id=publication.id,
        version_number=next_version,
    )
    version = SkillPublicationVersion(
        id=str(uuid.uuid4()),
        publication_id=publication.id,
        version_number=next_version,
        status="PENDING",
        snapshot_path=snapshot.snapshot_path,
        content_sha256=snapshot.content_sha256,
        file_count=snapshot.file_count,
        total_size=snapshot.total_size,
        submitted_by=user_id,
    )
    session.add(version)
    publication.status = "PENDING"
    await session.flush()
    await notify_skill_publication_reviewers(
        session,
        publication=publication,
        version=version,
        submitted_by=user,
    )
    return _publication_payload(publication, version)


async def list_my_publication_summaries(
    session: AsyncSession,
    *,
    user_id: int,
    skill_ids: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    query = select(SkillPublication).where(SkillPublication.source_user_id == int(user_id))
    if skill_ids:
        query = query.where(SkillPublication.source_personal_skill_id.in_(skill_ids))
    result = await session.execute(query)
    summaries: dict[str, dict[str, Any]] = {}
    for publication in result.scalars().all():
        versions = await _versions_for_publication(session, publication.id)
        latest = versions[0] if versions else None
        summaries[publication.source_personal_skill_id] = _publication_payload(publication, latest)
    return summaries


async def list_pending_publications(session: AsyncSession) -> list[dict[str, Any]]:
    result = await session.execute(
        select(SkillPublicationVersion, SkillPublication)
        .join(SkillPublication, SkillPublication.id == SkillPublicationVersion.publication_id)
        .where(SkillPublicationVersion.status == "PENDING")
        .order_by(SkillPublicationVersion.submitted_at.asc())
    )
    return [_publication_payload(publication, version) for version, publication in result.all()]


async def get_publication_version(
    session: AsyncSession,
    *,
    version_id: str,
    include_snapshot: bool = False,
) -> dict[str, Any]:
    result = await session.execute(
        select(SkillPublicationVersion, SkillPublication)
        .join(SkillPublication, SkillPublication.id == SkillPublicationVersion.publication_id)
        .where(SkillPublicationVersion.id == version_id)
    )
    row = result.first()
    if not row:
        raise PublicationNotFoundError("publication version not found")
    version, publication = row
    payload = _publication_payload(publication, version)
    payload.update(
        {
            "snapshot_path": version.snapshot_path if include_snapshot else None,
            "file_count": version.file_count,
            "total_size": version.total_size,
            "submitted_by": version.submitted_by,
            "submitted_at": version.submitted_at.isoformat() if version.submitted_at else None,
            "reviewed_by": version.reviewed_by,
            "reviewed_at": version.reviewed_at.isoformat() if version.reviewed_at else None,
            "review_comment": version.review_comment,
            "materialized_path": version.materialized_path,
        }
    )
    return payload


async def approve_publication(
    session: AsyncSession,
    *,
    version_id: str,
    reviewer: dict[str, Any],
) -> dict[str, Any]:
    result = await session.execute(
        select(SkillPublicationVersion, SkillPublication)
        .join(SkillPublication, SkillPublication.id == SkillPublicationVersion.publication_id)
        .where(SkillPublicationVersion.id == version_id)
    )
    row = result.first()
    if not row:
        raise PublicationNotFoundError("publication version not found")
    version, publication = row
    if version.status != "PENDING":
        raise PublicationConflictError("publication version is no longer pending")
    reviewer_id = _user_id(reviewer)
    platform_id = publication.platform_skill_id or _platform_skill_id(publication.name, publication.id)
    materialized = materialize_snapshot(
        snapshot_path=version.snapshot_path,
        platform_skill_id=platform_id,
        version_number=version.version_number,
        publication_id=publication.id,
    )
    await session.execute(
        update(SkillPublicationVersion)
        .where(
            SkillPublicationVersion.publication_id == publication.id,
            SkillPublicationVersion.status == "APPROVED",
        )
        .values(status="SUPERSEDED")
    )
    now = datetime.now()
    publication.platform_skill_id = platform_id
    publication.current_version = version.version_number
    publication.status = "PUBLISHED"
    publication.updated_at = now
    version.status = "APPROVED"
    version.reviewed_by = reviewer_id
    version.reviewed_at = now
    version.published_at = now
    version.materialized_path = materialized.materialized_path
    await session.flush()
    return _publication_payload(publication, version)


async def reject_publication(
    session: AsyncSession,
    *,
    version_id: str,
    reviewer: dict[str, Any],
    comment: str,
) -> dict[str, Any]:
    if not (comment or "").strip():
        raise ValueError("reject comment is required")
    result = await session.execute(
        select(SkillPublicationVersion, SkillPublication)
        .join(SkillPublication, SkillPublication.id == SkillPublicationVersion.publication_id)
        .where(SkillPublicationVersion.id == version_id)
    )
    row = result.first()
    if not row:
        raise PublicationNotFoundError("publication version not found")
    version, publication = row
    if version.status != "PENDING":
        raise PublicationConflictError("publication version is no longer pending")
    version.status = "REJECTED"
    version.reviewed_by = _user_id(reviewer)
    version.reviewed_at = datetime.now()
    version.review_comment = comment.strip()
    if publication.current_version is None:
        publication.status = "PENDING"
    await session.flush()
    return _publication_payload(publication, version)
