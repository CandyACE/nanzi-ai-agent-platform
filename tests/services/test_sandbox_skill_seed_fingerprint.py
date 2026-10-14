"""沙箱技能 ``.seed`` 失效判据：必须覆盖「技能集合」与「权限」，而不只是公共库文件。

回归的是三个曾经漏掉的场景——它们的共同症状都是「平台说这个技能不存在/已禁用，
模型在沙箱里却还能翻到甚至执行」：

1. 管理员**禁用**某个公共技能（只改权限、不动技能文件）；
2. 个人技能被**删除**或改版（个人技能库根本不在旧指纹里）；
3. 已被装备过的分区（``skills/<agent_id>/``）只重建 ``.seed`` 清不掉残留。
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.services.ai.runtime.agentscope import workspace as ws

pytestmark = pytest.mark.no_infrastructure


def _write_skill(root: Path, name: str, body: str = "body") -> Path:
    target = root / name
    target.mkdir(parents=True, exist_ok=True)
    (target / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: d\n---\n\n{body}\n", encoding="utf-8"
    )
    return target


@pytest.fixture
def env(tmp_path):
    """公共技能库 + 用户工作区（含个人技能源与物化技能目录）。"""
    public = tmp_path / "public_skills"
    public.mkdir()
    _write_skill(public, "pub-a")
    workdir = tmp_path / "agent_workspaces" / "u__1"
    personal = workdir / "skills"
    personal.mkdir(parents=True)
    return {"public": public, "workdir": str(workdir), "personal": personal}


@pytest.mark.asyncio
async def test_fingerprint_changes_when_public_skill_edited(env):
    """基线：公共技能文件改动要让指纹变（原有行为，不能回归掉）。"""
    before = await _fp(env)
    _write_skill(env["public"], "pub-b")
    after = await _fp(env)
    assert before != after


@pytest.mark.asyncio
async def test_fingerprint_changes_when_skill_disabled(env):
    """★ 核心回归：禁用是改权限、不动文件，旧指纹察觉不到。"""
    before = await _fp(env)
    after = await _fp(env, forbidden=["pub-a"])
    assert before != after, "禁用集合变化必须改变 seed 指纹，否则沙箱永远留着已禁用技能"


@pytest.mark.asyncio
async def test_fingerprint_changes_when_personal_skill_removed(env):
    """★ 核心回归：个人技能库原先完全不在指纹里，删除后 .seed 不会失效。"""
    _write_skill(env["personal"], "mine")
    before = await _fp(env)
    import shutil

    shutil.rmtree(env["personal"] / "mine")
    after = await _fp(env)
    assert before != after, "删除个人技能必须改变 seed 指纹，否则沙箱留着鬼影技能"


@pytest.mark.asyncio
async def test_fingerprint_changes_when_personal_skill_edited(env):
    _write_skill(env["personal"], "mine", body="v1")
    before = await _fp(env)
    _write_skill(env["personal"], "mine", body="v2")
    after = await _fp(env)
    assert before != after


@pytest.mark.asyncio
async def test_disable_event_actually_invalidates_seed(env):
    """端到端：指纹变了 → .seed 被删 → initialize() 会按最新 skill_paths 重打包。"""
    skills_dir = Path(ws._sandbox_skills_dir(env["workdir"]))
    seed = skills_dir / ws.SANDBOX_SKILL_SEED_DIR_NAME
    _write_skill(seed, "pub-a")

    before = await _fp(env)
    ws._write_sandbox_skills_fingerprint(env["workdir"], before)
    # 未变化 → 不作废
    invalidated, _ = ws._invalidate_stale_sandbox_skill_seed(env["workdir"], before)
    assert invalidated is False
    assert seed.is_dir()

    changed = await _fp(env, forbidden=["pub-a"])
    invalidated, committed = ws._invalidate_stale_sandbox_skill_seed(
        env["workdir"], changed
    )
    assert invalidated is True
    assert committed == changed
    assert not seed.exists(), ".seed 必须被删除，否则 AgentScope 永不重打包"


@pytest.mark.asyncio
async def test_forbidden_lookup_failure_degrades_without_raising(env):
    """权限服务抖动时不能连累技能链路：退化为不含权限的指纹并告警。"""
    with patch.object(
        ws, "_platform_public_skills_fingerprint", lambda: "public-fp"
    ), patch(
        "app.services.ai.skills.policy.get_forbidden_skill_ids",
        AsyncMock(side_effect=RuntimeError("permission service down")),
    ):
        fingerprint = await ws._sandbox_skills_seed_fingerprint(env["workdir"])
    assert fingerprint, "读不到禁用集合也要给出指纹，而不是让容器初始化失败"


# ---------------------------------------------------------------------------
# 分区同步：清掉「上一版 seed 装过、这一版没有」的条目
# ---------------------------------------------------------------------------
def _seed_with(env, names):
    skills_dir = Path(ws._sandbox_skills_dir(env["workdir"]))
    seed = skills_dir / ws.SANDBOX_SKILL_SEED_DIR_NAME
    for name in names:
        _write_skill(seed, name)
    return skills_dir, seed


def test_sync_removes_deleted_personal_skill_from_partition(env):
    """★ 核心回归：被删的个人技能必须从已装备分区里消失。

    旧实现只按「公共技能名单」清理，个人技能不在名单里 → 永远不会被清掉。
    """
    skills_dir, seed = _seed_with(env, ["pub-a", "mine"])
    partition = skills_dir / "default"
    _write_skill(partition, "pub-a")
    _write_skill(partition, "mine")
    # 账本记录上一版 seed 装过这两个
    ws._write_sandbox_skill_manifest(env["workdir"], ["pub-a", "mine"])

    # 个人技能被删：新 seed 里只剩 pub-a
    import shutil

    shutil.rmtree(seed / "mine")
    synced = ws._sync_public_skills_into_sandbox_partitions(env["workdir"])

    assert synced >= 1
    assert (partition / "pub-a" / "SKILL.md").is_file()
    assert not (partition / "mine").exists(), "被删的个人技能不该留在分区里"


def test_sync_preserves_agent_authored_skill(env):
    """★ 反向保护：agent 自己用技能 API 建的技能绝不能被清理连带删掉。"""
    skills_dir, seed = _seed_with(env, ["pub-a"])
    partition = skills_dir / "default"
    _write_skill(partition, "pub-a")
    _write_skill(partition, "agent-made")
    ws._write_sandbox_skill_manifest(env["workdir"], ["pub-a"])

    ws._sync_public_skills_into_sandbox_partitions(env["workdir"])

    assert (partition / "agent-made" / "SKILL.md").is_file(), "agent 自建技能必须保留"


def test_sync_without_manifest_falls_back_to_public_names(env):
    """老部署升级时没有账本，仍要能清掉「曾是公共技能但现在不在 seed」的残留。"""
    skills_dir, seed = _seed_with(env, ["pub-a"])
    partition = skills_dir / "default"
    _write_skill(partition, "pub-a")
    _write_skill(partition, "pub-removed")  # 曾发布过、现已从 seed 消失
    _write_skill(partition, "agent-made")

    removed = {"pub-a", "pub-removed"}
    with patch.object(ws, "_public_skill_directory_names", lambda: removed):
        ws._sync_public_skills_into_sandbox_partitions(env["workdir"])

    assert not (partition / "pub-removed").exists(), "无账本时应按公共名单兜底清理"
    assert (partition / "agent-made").is_dir(), "兜底清理也不能误删 agent 自建技能"


def test_sync_copies_new_personal_skill_into_partition(env):
    """新增的个人技能也要同步进老分区（个人技能此前完全不在同步范围内）。"""
    skills_dir, seed = _seed_with(env, ["pub-a"])
    partition = skills_dir / "default"
    _write_skill(partition, "pub-a")
    ws._write_sandbox_skill_manifest(env["workdir"], ["pub-a"])

    _write_skill(seed, "mine-fresh")
    ws._sync_public_skills_into_sandbox_partitions(env["workdir"])

    assert (partition / "mine-fresh" / "SKILL.md").is_file()


def test_manifest_is_hidden_and_not_treated_as_skill(env):
    """账本写在技能目录下，点开头，不能被当成技能条目或参与同步。"""
    skills_dir, seed = _seed_with(env, ["pub-a"])
    ws._write_sandbox_skill_manifest(env["workdir"], ["pub-a"])
    path = skills_dir / ws.SANDBOX_SKILL_MANIFEST_NAME
    assert path.name.startswith(".")
    assert json.loads(path.read_text(encoding="utf-8"))["entries"] == ["pub-a"]
    visible = ws._list_visible_entries(str(skills_dir))
    assert ws.SANDBOX_SKILL_MANIFEST_NAME not in visible


def test_manifest_survives_corruption(env):
    """账本损坏不能让同步炸掉，退化为「只认公共技能」。"""
    skills_dir = Path(ws._sandbox_skills_dir(env["workdir"]))
    skills_dir.mkdir(parents=True, exist_ok=True)
    manifest = skills_dir / ws.SANDBOX_SKILL_MANIFEST_NAME
    manifest.write_text("{ not json", encoding="utf-8")
    assert ws._read_sandbox_skill_manifest(env["workdir"]) == set()


def test_invalidate_records_manifest_before_deleting_seed(env):
    """.seed 删除后仍要知道上一版装过什么，所以账本必须先落盘。"""
    skills_dir, seed = _seed_with(env, ["pub-a", "mine"])
    with patch.object(ws, "_platform_public_skills_fingerprint", lambda: "fp-1"):
        invalidated, _ = ws._invalidate_stale_sandbox_skill_seed(env["workdir"], "fp-2")
    assert invalidated is True
    assert not seed.exists()
    assert ws._read_sandbox_skill_manifest(env["workdir"]) == {"pub-a", "mine"}


@pytest.mark.asyncio
async def _fp(env, forbidden=()):
    with (
        patch.object(
            ws,
            "_platform_public_skills_fingerprint",
            lambda: ws._dir_tree_fingerprint(str(env["public"])),
        ),
        patch(
            "app.services.ai.skills.policy.get_forbidden_skill_ids",
            AsyncMock(return_value=set(forbidden)),
        ),
    ):
        return await ws._sandbox_skills_seed_fingerprint(env["workdir"])
