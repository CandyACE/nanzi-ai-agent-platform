import os
import time

import pytest

from scripts.repair_session_skills import (
    iter_session_skill_dirs,
    prune_stale_session_skills,
    relink_skill_files,
)

pytestmark = pytest.mark.no_infrastructure


def _make_linked_skill(session_dir, source):
    skills_dir = session_dir / "skills"
    skills_dir.mkdir(parents=True)
    target = skills_dir / "SKILL.md"
    os.link(source, target)
    return target


def test_iter_session_skill_dirs_ignores_personal_skill_sources(tmp_path):
    """只认 sessions/<cid>/skills：个人技能源目录（<user_key>/skills）绝不能被扫到。"""
    user_root = tmp_path / "u1"
    (user_root / "skills" / "brainstorming").mkdir(parents=True)
    session_skills = user_root / "sessions" / "c1" / "skills"
    session_skills.mkdir(parents=True)

    found = [skills for _session, skills in iter_session_skill_dirs(str(user_root))]

    assert found == [str(session_skills)]


def test_relink_breaks_hard_links_and_isolates_writes(tmp_path):
    """历史硬链接副本必须断开：否则从会话副本写入会顺着 inode 改到平台技能源。"""
    source = tmp_path / "source" / "SKILL.md"
    source.parent.mkdir()
    source.write_text("v1", encoding="utf-8")
    linked = _make_linked_skill(tmp_path / "session", source)
    assert os.stat(linked).st_nlink == 2

    scanned, fixed = relink_skill_files(str(linked.parent), apply=True)

    assert (scanned, fixed) == (1, 1)
    assert os.stat(linked).st_nlink == 1

    linked.write_text("v2", encoding="utf-8")
    assert source.read_text(encoding="utf-8") == "v1"


def test_relink_dry_run_leaves_links_in_place(tmp_path):
    source = tmp_path / "source" / "SKILL.md"
    source.parent.mkdir()
    source.write_text("v1", encoding="utf-8")
    linked = _make_linked_skill(tmp_path / "session", source)

    scanned, fixed = relink_skill_files(str(linked.parent), apply=False)

    assert (scanned, fixed) == (1, 0)
    assert os.stat(linked).st_nlink == 2


def _make_snapshot(user_root, conversation_id, *, age_days):
    skills_dir = user_root / "sessions" / conversation_id / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text("x", encoding="utf-8")
    if age_days:
        stale = time.time() - age_days * 86400
        os.utime(skills_dir, (stale, stale))
        os.utime(skills_dir.parent, (stale, stale))
    return skills_dir


def test_prune_stale_removes_only_old_snapshots(tmp_path):
    """陈旧快照可安全删除（下次对话重建）；近期仍活跃的会话绝不能被误删。"""
    user_root = tmp_path / "agent_workspaces" / "u1"
    old_skills = _make_snapshot(user_root, "old", age_days=40)
    fresh_skills = _make_snapshot(user_root, "fresh", age_days=0)

    candidates, removed, _freed = prune_stale_session_skills(
        str(user_root), older_than_days=30, apply=True
    )

    assert (candidates, removed) == (1, 1)
    assert not old_skills.exists()
    assert fresh_skills.exists()


def test_prune_stale_dry_run_keeps_snapshots(tmp_path):
    user_root = tmp_path / "agent_workspaces" / "u1"
    old_skills = _make_snapshot(user_root, "old", age_days=40)

    candidates, removed, _freed = prune_stale_session_skills(
        str(user_root), older_than_days=30, apply=False
    )

    assert (candidates, removed) == (1, 0)
    assert old_skills.exists()


def test_session_skill_snapshot_dir_prefers_seed_layout(tmp_path):
    """快照现在住在 ``skills/.seed``；老会话（平铺）回退到 ``skills/`` 根。"""
    from scripts.repair_session_skills import session_skill_snapshot_dir

    skills_dir = tmp_path / "session" / "skills"
    (skills_dir / ".seed").mkdir(parents=True)
    assert session_skill_snapshot_dir(str(skills_dir)) == str(skills_dir / ".seed")

    flat = tmp_path / "flat" / "skills"
    flat.mkdir(parents=True)
    assert session_skill_snapshot_dir(str(flat)) == str(flat)


def test_relink_reads_seed_snapshot_and_prune_drops_the_ledger(tmp_path):
    """``.seed`` 里的硬链接照样要断开；删快照时平台账本必须一起清掉（否则留悬空记录）。"""
    from scripts.repair_session_skills import session_skill_snapshot_dir

    user_root = tmp_path / "agent_workspaces" / "u1"
    session_dir = user_root / "sessions" / "c1"
    skills_dir = session_dir / "skills"
    seed_dir = skills_dir / ".seed" / "alpha"
    seed_dir.mkdir(parents=True)
    source = tmp_path / "source.md"
    source.write_text("v1", encoding="utf-8")
    linked = seed_dir / "SKILL.md"
    os.link(source, linked)
    ledger = session_dir / ".session_skills.json"
    ledger.write_text("{}", encoding="utf-8")

    snapshot = session_skill_snapshot_dir(str(skills_dir))
    assert snapshot == str(skills_dir / ".seed")
    scanned, fixed = relink_skill_files(snapshot, apply=True)
    assert (scanned, fixed) == (1, 1)
    assert os.stat(linked).st_nlink == 1

    stale = time.time() - 40 * 86400
    os.utime(skills_dir, (stale, stale))
    os.utime(session_dir, (stale, stale))

    candidates, removed, _freed = prune_stale_session_skills(
        str(user_root), older_than_days=30, apply=True
    )

    assert (candidates, removed) == (1, 1)
    assert not skills_dir.exists()
    assert not ledger.exists()
