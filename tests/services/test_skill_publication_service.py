from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.models.skill_publication import SkillPublication, SkillPublicationVersion
from app.services.skill_publication_service import (
    create_personal_skill_snapshot,
    materialize_snapshot,
)


pytestmark = pytest.mark.no_infrastructure


def _write_skill(root: Path, skill_id: str, *, body: str = "# v1\n") -> Path:
    skill_dir = root / skill_id
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {skill_id}\ndescription: test\n---\n\n{body}",
        encoding="utf-8",
    )
    (skill_dir / "references").mkdir()
    (skill_dir / "references" / "guide.md").write_text("guide", encoding="utf-8")
    return skill_dir


def test_publication_models_use_stable_tables_and_required_columns():
    assert SkillPublication.__tablename__ == "skill_publications"
    assert SkillPublicationVersion.__tablename__ == "skill_publication_versions"
    assert {
        "platform_skill_id",
        "source_user_id",
        "source_personal_skill_id",
        "current_version",
        "status",
    } <= set(SkillPublication.__table__.columns.keys())
    assert {
        "publication_id",
        "version_number",
        "snapshot_path",
        "content_sha256",
        "file_count",
        "total_size",
        "review_comment",
    } <= set(SkillPublicationVersion.__table__.columns.keys())


def test_create_snapshot_is_isolated_from_personal_edits(tmp_path):
    personal_root = tmp_path / "personal"
    skill_dir = _write_skill(personal_root, "summarizer", body="# original\n")
    skills_root = tmp_path / "global"
    settings = SimpleNamespace(SKILLS_DIR=str(skills_root))
    user = {"user_id": 7, "user_name": "tester"}

    with patch(
        "app.services.skill_publication_service.get_user_personal_skills_dir",
        return_value=str(personal_root),
    ), patch("app.services.skill_publication_service.settings", settings):
        snapshot = create_personal_skill_snapshot(
            user=user,
            skill_id="summarizer",
            publication_id="publication-1",
            version_number=1,
        )

    original_hash = snapshot.content_sha256
    (skill_dir / "SKILL.md").write_text("---\nname: summarizer\n---\n\n# changed\n", encoding="utf-8")

    assert Path(snapshot.snapshot_path, "SKILL.md").read_text(encoding="utf-8").endswith("# original\n")
    assert snapshot.content_sha256 == original_hash
    assert snapshot.file_count == 2


def test_create_snapshot_rejects_hidden_files_and_symlinks(tmp_path):
    personal_root = tmp_path / "personal"
    skill_dir = _write_skill(personal_root, "unsafe")
    (skill_dir / ".env").write_text("TOKEN=secret", encoding="utf-8")
    settings = SimpleNamespace(SKILLS_DIR=str(tmp_path / "global"))

    with patch(
        "app.services.skill_publication_service.get_user_personal_skills_dir",
        return_value=str(personal_root),
    ), patch("app.services.skill_publication_service.settings", settings):
        with pytest.raises(ValueError, match="hidden"):
            create_personal_skill_snapshot(
                user={"user_id": 7},
                skill_id="unsafe",
                publication_id="publication-2",
                version_number=1,
            )


def test_materialize_snapshot_uses_unique_platform_id_and_preserves_source(tmp_path):
    snapshot_root = tmp_path / "snapshots" / "publication-3" / "v1"
    snapshot_root.mkdir(parents=True)
    (snapshot_root / "SKILL.md").write_text(
        "---\nname: Shared\nenabled: true\n---\n\n# v1\n",
        encoding="utf-8",
    )
    skills_root = tmp_path / "global"
    source_root = tmp_path / "personal" / "shared"
    source_root.mkdir(parents=True)
    (source_root / "SKILL.md").write_text("personal", encoding="utf-8")
    settings = SimpleNamespace(SKILLS_DIR=str(skills_root))

    with patch("app.services.skill_publication_service.settings", settings):
        result = materialize_snapshot(
            snapshot_path=str(snapshot_root),
            platform_skill_id="public-shared-1234abcd",
            version_number=1,
        )

    active_file = skills_root / "public-shared-1234abcd" / "SKILL.md"
    assert result.materialized_path == str(skills_root / "public-shared-1234abcd")
    assert active_file.exists()
    assert active_file.read_text(encoding="utf-8").endswith("# v1\n")
    assert (source_root / "SKILL.md").read_text(encoding="utf-8") == "personal"
