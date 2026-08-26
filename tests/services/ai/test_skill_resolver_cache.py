import os
from pathlib import Path
from unittest.mock import PropertyMock

import pytest

from app.services.ai.skill_resolver import list_skill_metas


pytestmark = pytest.mark.no_infrastructure


def test_list_skill_metas_reuses_unchanged_directory_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    global_root = tmp_path / "global_skills"
    skill_root = global_root / "demo-skill"
    skill_root.mkdir(parents=True)
    (skill_root / "SKILL.md").write_text(
        "---\nname: Demo\ndescription: demo\n---\n",
        encoding="utf-8",
    )

    parse_calls = 0

    def parse_frontmatter(skill_id: str, skill_md_path: str):
        nonlocal parse_calls
        parse_calls += 1
        return {
            "id": skill_id,
            "name": "Demo",
            "description": "demo",
            "enabled": "true",
        }

    monkeypatch.setattr(
        "app.services.ai.skill_resolver._parse_skill_frontmatter",
        parse_frontmatter,
    )

    mock_skills_dir = PropertyMock(return_value=str(global_root))
    monkeypatch.setattr("app.core.config.Settings.SKILLS_DIR", mock_skills_dir)
    first = list_skill_metas()
    second = list_skill_metas()

    assert [meta["id"] for meta in first] == ["demo-skill"]
    assert [meta["id"] for meta in second] == ["demo-skill"]
    assert parse_calls == 1


def test_list_skill_metas_invalidates_when_skill_file_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    global_root = tmp_path / "global_skills"
    skill_root = global_root / "demo-skill"
    skill_root.mkdir(parents=True)
    skill_md = skill_root / "SKILL.md"
    skill_md.write_text("---\nname: Before\n---\n", encoding="utf-8")

    def parse_frontmatter(skill_id: str, skill_md_path: str):
        content = Path(skill_md_path).read_text(encoding="utf-8")
        return {
            "id": skill_id,
            "name": "After" if "After" in content else "Before",
            "description": "",
            "enabled": "true",
        }

    monkeypatch.setattr(
        "app.services.ai.skill_resolver._parse_skill_frontmatter",
        parse_frontmatter,
    )
    monkeypatch.setattr(
        "app.core.config.Settings.SKILLS_DIR",
        PropertyMock(return_value=str(global_root)),
    )

    first = list_skill_metas()
    previous_stat = skill_md.stat()
    skill_md.write_text("---\nname: After\n---\n", encoding="utf-8")
    os.utime(
        skill_md,
        ns=(previous_stat.st_atime_ns, previous_stat.st_mtime_ns + 1_000_000),
    )
    second = list_skill_metas()

    assert first[0]["name"] == "Before"
    assert second[0]["name"] == "After"


def test_list_skill_metas_returns_isolated_metadata_copies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    global_root = tmp_path / "global_skills"
    skill_root = global_root / "demo-skill"
    skill_root.mkdir(parents=True)
    (skill_root / "SKILL.md").write_text("---\nname: Demo\n---\n", encoding="utf-8")
    monkeypatch.setattr(
        "app.core.config.Settings.SKILLS_DIR",
        PropertyMock(return_value=str(global_root)),
    )

    first = list_skill_metas()
    first[0]["name"] = "mutated-by-caller"
    second = list_skill_metas()

    assert second[0]["name"] != "mutated-by-caller"
