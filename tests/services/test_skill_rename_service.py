"""技能重命名的行为测试。

重命名 = 目录改名 + **三处引用同步**。只改目录会得到「技能还在，但智能体挂不上、
会话里的 chip 指向不存在的 ID、发布记录变成源已不存在的孤儿」这种静默断链，
所以这里既验证拒绝条件，也验证同步编排与报告内容。
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from app.services import skill_rename_service as svc

pytestmark = pytest.mark.no_infrastructure


@pytest.fixture
def skill_tree(tmp_path):
    root = tmp_path / "skills"
    (root / "old-skill").mkdir(parents=True)
    (root / "old-skill" / "SKILL.md").write_text("# 旧技能\n", encoding="utf-8")
    (root / "old-skill" / "run.py").write_text("print(1)\n", encoding="utf-8")
    (root / "taken").mkdir()
    (root / "taken" / "SKILL.md").write_text("# 已存在\n", encoding="utf-8")
    return root


# ---------------------------------------------------------------------------
# ID 校验
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("bad", ["", "   ", "中文技能", "with space", "a/b", "a.b", "a" * 129])
def test_rejects_invalid_new_id(bad):
    with pytest.raises(svc.SkillRenameError):
        svc.validate_new_skill_id(bad)


@pytest.mark.parametrize("reserved", sorted(svc.RESERVED_SKILL_IDS))
def test_rejects_reserved_new_id(reserved):
    """保留字会被 /skills 下更早注册的字面路由遮蔽。"""
    with pytest.raises(svc.SkillRenameError):
        svc.validate_new_skill_id(reserved)


def test_accepts_valid_new_id():
    assert svc.validate_new_skill_id("  new-skill_2  ") == "new-skill_2"


# ---------------------------------------------------------------------------
# 目录改名
# ---------------------------------------------------------------------------
def test_rename_directory_moves_content(skill_tree):
    new_dir = svc.rename_skill_directory(
        str(skill_tree / "old-skill"), new_skill_id="new-skill"
    )
    assert new_dir == str(skill_tree / "new-skill")
    assert (skill_tree / "new-skill" / "SKILL.md").read_text(encoding="utf-8") == "# 旧技能\n"
    assert (skill_tree / "new-skill" / "run.py").is_file()
    assert not (skill_tree / "old-skill").exists()


def test_rename_directory_refuses_existing_target(skill_tree):
    with pytest.raises(svc.SkillRenameError, match="已被占用"):
        svc.rename_skill_directory(str(skill_tree / "old-skill"), new_skill_id="taken")
    # 两个技能都必须原样保留
    assert (skill_tree / "old-skill" / "SKILL.md").is_file()
    assert (skill_tree / "taken" / "SKILL.md").read_text(encoding="utf-8") == "# 已存在\n"


def test_rename_directory_refuses_same_id(skill_tree):
    with pytest.raises(svc.SkillRenameError, match="相同"):
        svc.rename_skill_directory(str(skill_tree / "old-skill"), new_skill_id="old-skill")


def test_rename_directory_refuses_non_skill_dir(skill_tree):
    (skill_tree / "not-a-skill").mkdir()
    with pytest.raises(svc.SkillRenameError, match="SKILL.md"):
        svc.rename_skill_directory(str(skill_tree / "not-a-skill"), new_skill_id="moved")


def test_rename_directory_refuses_missing_source(tmp_path):
    with pytest.raises(svc.SkillRenameError, match="不存在"):
        svc.rename_skill_directory(str(tmp_path / "nope"), new_skill_id="anything")


# ---------------------------------------------------------------------------
# 引用同步
# ---------------------------------------------------------------------------
class _FakeRedis:
    """最小 Redis 替身：支持 scan/get/set。"""

    def __init__(self, store):
        self.store = store

    async def scan(self, cursor=0, match=None, count=200):
        return 0, list(self.store.keys())

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value):
        self.store[key] = value


@pytest.mark.asyncio
async def test_sync_conversation_mounts_rewrites_skill_ids(monkeypatch):
    """会话挂载列表里的技能 ID 必须被改写，其它字段保持不变。"""
    store = {
        "conversation:1:c1:resource_scope_v1": json.dumps(
            {
                "project_name": "p",
                "skills": [
                    {"id": "old-skill", "name": "旧", "scope": "global"},
                    {"id": "other", "name": "别的", "scope": "global"},
                ],
            }
        ),
        "conversation:1:c2:resource_scope_v1": json.dumps({"skills": [{"id": "other"}]}),
    }
    fake = _FakeRedis(store)
    monkeypatch.setattr("app.core.redis.get_redis", AsyncMock(return_value=fake))

    updated = await svc.sync_conversation_mounts(old_skill_id="old-skill", new_skill_id="new-skill")

    assert updated == 1
    c1 = json.loads(store["conversation:1:c1:resource_scope_v1"])
    assert [item["id"] for item in c1["skills"]] == ["new-skill", "other"]
    # 不相关的会话不应被改写
    assert json.loads(store["conversation:1:c2:resource_scope_v1"]) == {
        "skills": [{"id": "other"}]
    }


@pytest.mark.asyncio
async def test_sync_conversation_mounts_survives_redis_failure(monkeypatch):
    """Redis 不可用不能让重命名失败：目录已经改好了。"""
    monkeypatch.setattr(
        "app.core.redis.get_redis", AsyncMock(side_effect=RuntimeError("redis down"))
    )
    assert await svc.sync_conversation_mounts(old_skill_id="a", new_skill_id="b") == 0


# ---------------------------------------------------------------------------
# 编排与报告
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_rename_skill_syncs_personal_publications(skill_tree, monkeypatch):
    lineage = AsyncMock(return_value=3)
    mounts = AsyncMock(return_value=5)
    monkeypatch.setattr(svc, "sync_publication_lineage", lineage)
    monkeypatch.setattr(svc, "sync_conversation_mounts", mounts)

    report = await svc.rename_skill(
        AsyncMock(),
        current_dir=str(skill_tree / "old-skill"),
        old_skill_id="old-skill",
        new_skill_id="new-skill",
        scope="personal",
    )

    assert report["skill_id"] == "new-skill"
    assert report["previous_skill_id"] == "old-skill"
    assert report["synced"]["publications"] == 3
    assert report["synced"]["conversations"] == 5
    assert report["warnings"] == []
    assert (skill_tree / "new-skill" / "SKILL.md").is_file()
    lineage.assert_awaited_once()


@pytest.mark.asyncio
async def test_rename_skill_syncs_agent_bindings_for_global(skill_tree, monkeypatch):
    bindings = AsyncMock(return_value=["agent-1"])
    mounts = AsyncMock(return_value=0)
    monkeypatch.setattr(svc, "sync_agent_bindings", bindings)
    monkeypatch.setattr(svc, "sync_conversation_mounts", mounts)

    report = await svc.rename_skill(
        AsyncMock(),
        current_dir=str(skill_tree / "old-skill"),
        old_skill_id="old-skill",
        new_skill_id="new-skill",
        scope="global",
    )

    assert report["synced"]["agents"] == ["agent-1"]
    bindings.assert_awaited_once()


@pytest.mark.asyncio
async def test_rename_skill_reports_warning_when_sync_fails(skill_tree, monkeypatch):
    """引用同步失败不回滚目录改名，但必须如实警告，不能假装成功了。"""
    monkeypatch.setattr(
        svc, "sync_publication_lineage", AsyncMock(side_effect=RuntimeError("db down"))
    )
    monkeypatch.setattr(svc, "sync_conversation_mounts", AsyncMock(return_value=0))

    report = await svc.rename_skill(
        AsyncMock(),
        current_dir=str(skill_tree / "old-skill"),
        old_skill_id="old-skill",
        new_skill_id="new-skill",
        scope="personal",
    )

    assert report["warnings"], "同步失败必须出现在 warnings 里"
    # 目录改名依然生效
    assert (skill_tree / "new-skill" / "SKILL.md").is_file()
    assert not (skill_tree / "old-skill").exists()


@pytest.mark.asyncio
async def test_rename_skill_rejects_taken_id_before_touching_disk(skill_tree):
    with pytest.raises(svc.SkillRenameError):
        await svc.rename_skill(
            AsyncMock(),
            current_dir=str(skill_tree / "old-skill"),
            old_skill_id="old-skill",
            new_skill_id="taken",
            scope="personal",
        )
    assert (skill_tree / "old-skill" / "SKILL.md").is_file()
