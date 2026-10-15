"""沙箱技能 ``.seed`` 失效判据：必须覆盖「技能集合」与「权限」，而不只是公共库文件。

回归的是三个曾经漏掉的场景——它们的共同症状都是「平台说这个技能不存在/已禁用，
模型在沙箱里却还能翻到甚至执行」：

1. 管理员**禁用**某个公共技能（只改权限、不动技能文件）；
2. 个人技能被**删除**或改版（个人技能库根本不在旧指纹里）；
3. 已被装备过的分区（``skills/<agent_id>/``）只重建 ``.seed`` 清不掉残留。
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

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
    synced, failed = ws._sync_public_skills_into_sandbox_partitions(env["workdir"])

    assert synced >= 1
    assert failed == []
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


# ---------------------------------------------------------------------------
# 沙箱缓存键必须区分技能集合（沙箱按用户复用，不按智能体）
# ---------------------------------------------------------------------------
def test_cache_token_is_order_and_duplicate_insensitive():
    """技能集合的语义是「装了哪些」：顺序与重复都不该造出第二个沙箱。"""
    a = ws._skill_paths_cache_token(["/skills/x", "/skills/y"])
    assert a == ws._skill_paths_cache_token(["/skills/y", "/skills/x"])
    assert a == ws._skill_paths_cache_token(["/skills/x", "/skills/y", "/skills/x"])
    assert a != ws._skill_paths_cache_token(["/skills/x"])


def test_cache_token_distinguishes_different_sets():
    """不同智能体白名单必须有不同令牌，否则会命中别人的沙箱。"""
    token_a = ws._skill_paths_cache_token(["/s/pub-a"])
    token_b = ws._skill_paths_cache_token(["/s/pub-b"])
    assert token_a != token_b


def test_cache_token_handles_empty_and_missing():
    """空集合（未配置白名单 = 全部技能）要有稳定且不与「有技能」混淆的令牌。"""
    empty = ws._skill_paths_cache_token([])
    assert empty == ws._skill_paths_cache_token(None)
    assert empty == ws._skill_paths_cache_token(["", "   "])
    assert empty != ws._skill_paths_cache_token(["/s/anything"])


def test_cache_token_is_short_and_distinguishes_sources():
    """令牌是沙箱物理身份（容器名/目录名/指纹）的一部分，必须区分来源且够短。

    同名技能可能同时存在于公共库与个人库（内容不同）→ 令牌必须带来源路径而不是只取
    basename，否则两个技能集合会共用同一台容器、同一份 ``.seed``。
    """
    same_a = ws._skill_paths_cache_token(["/a/b/skills/mine"])
    same_b = ws._skill_paths_cache_token(["/a/b/skills/mine"])
    assert same_a == same_b
    token = ws._skill_paths_cache_token(["/s/" + "x" * 200])
    assert len(token) <= 24, "令牌不能把完整路径塞进缓存键"
    # 同名不同源必须分开；空集合有稳定哨兵值
    assert ws._skill_paths_cache_token(["/public/skills/mine"]) != ws._skill_paths_cache_token(
        ["/home/alice/skills/mine"]
    )
    assert ws._skill_paths_cache_token([]) == "noskills"
    assert ws._skill_paths_cache_token(None) == "noskills"


@pytest.mark.asyncio
async def test_acquire_separates_sandboxes_per_skill_set(tmp_path):
    """★ 核心回归：换了技能集合必须拿到另一个沙箱，而不是复用上一个智能体的。"""
    built = []
    workdir = tmp_path / "ws"

    async def fake_policy(skill_paths, **kwargs):
        built.append(list(skill_paths or []))
        instance = MagicMock()
        instance.is_alive = True
        instance.close = AsyncMock()
        return instance

    with patch.object(ws, "_policy_k8s_workspace", fake_policy):
        ws._k8s_workspace_cache.clear()
        ws._k8s_workspace_refcounts.clear()
        ws._k8s_workspace_last_used.clear()
        ws._k8s_workspace_locks.clear()
        try:
            _, key_a = await ws._acquire_k8s_workspace(
                root=str(workdir), user_key="u1", skill_paths=["/s/only-a"]
            )
            _, key_b = await ws._acquire_k8s_workspace(
                root=str(workdir), user_key="u1", skill_paths=["/s/only-b"]
            )
            # 同一集合应命中同一沙箱
            _, key_a2 = await ws._acquire_k8s_workspace(
                root=str(workdir), user_key="u1", skill_paths=["/s/only-a"]
            )
        finally:
            ws._k8s_workspace_cache.clear()
            ws._k8s_workspace_refcounts.clear()
            ws._k8s_workspace_last_used.clear()
            ws._k8s_workspace_locks.clear()

    assert key_a != key_b, "不同技能集合共用了沙箱 → 会看到不属于自己的技能"
    assert key_a == key_a2, "相同技能集合应复用沙箱，否则每次会话都重建容器"
    assert built == [["/s/only-a"], ["/s/only-b"]], "第二个集合不该复用第一个沙箱"


def test_find_cached_k8s_workspace_matches_by_user_prefix():
    """只读的状态/身份查询拿不到 skill_paths，必须能按用户前缀取到自己的沙箱。"""
    ws._k8s_workspace_cache.clear()
    try:
        marker = object()
        ws._k8s_workspace_cache["/data::u1::abc123::k8s"] = marker
        ws._k8s_workspace_cache["/data::u2::abc123::k8s"] = object()
        assert ws._find_cached_k8s_workspace("/data", "u1") is marker
        assert ws._find_cached_k8s_workspace("/data", "nobody") is None
        # 不同 root 不能串味
        assert ws._find_cached_k8s_workspace("/other", "u1") is None
    finally:
        ws._k8s_workspace_cache.clear()


def test_evict_for_user_still_matches_new_key_format():
    """逐出逻辑按 ``::user::`` 子串匹配，必须继续认得含技能令牌的新键。"""
    key = f"/data::u1::{ws._skill_paths_cache_token(['/s/a'])}::k8s"
    assert "::u1::" in key, "缓存键格式变化不能让按用户逐出失效"


# ---------------------------------------------------------------------------
# 物理沙箱身份 = 缓存条目身份（P0：容器/Pod 名、技能目录、指纹同源）
# ---------------------------------------------------------------------------


def test_physical_sandbox_identity_is_per_skill_set(tmp_path):
    """★ 核心回归：不同技能集合必须是**不同的物理沙箱**，不能只分缓存键。

    只分缓存键时，第二条条目会在 ``create_or_replace`` 里把第一条正在用的容器删掉重建，
    而第一条仍被当作可用（``is_alive`` 只是布尔属性），后续 Bash 全部打在已删除的容器上。
    """
    host_workdir = str(tmp_path / "agent_workspaces" / "u1")
    set_a = ["/public/skills/alpha"]
    set_b = ["/public/skills/beta"]

    assert ws._sandbox_workspace_id("u1", set_a) != ws._sandbox_workspace_id("u1", set_b)
    assert ws._docker_container_name(ws._sandbox_workspace_id("u1", set_a)) != (
        ws._docker_container_name(ws._sandbox_workspace_id("u1", set_b))
    )
    assert ws._sandbox_skills_dir(host_workdir, ws._skill_paths_cache_token(set_a)) != (
        ws._sandbox_skills_dir(host_workdir, ws._skill_paths_cache_token(set_b))
    )
    assert ws._k8s_pod_name(ws._sandbox_workspace_id("u1", set_a)) != ws._k8s_pod_name(
        ws._sandbox_workspace_id("u1", set_b)
    )
    # 空集合也要有稳定身份，且不能和任何非空集合撞名
    empty_id = ws._sandbox_workspace_id("u1", [])
    assert empty_id == "u1-noskills"
    assert empty_id != ws._sandbox_workspace_id("u1", set_a)


@pytest.mark.asyncio
async def test_acquire_docker_isolates_containers_per_skill_set(tmp_path):
    """★ 核心回归：acquire 必须把技能令牌带进 ``workspace_id``（容器名）。"""
    built: list[str | None] = []

    async def fake_policy(skill_paths, **kwargs):
        built.append(kwargs.get("workspace_id"))
        instance = MagicMock()
        instance.is_alive = True
        instance.close = AsyncMock()
        return instance

    with patch.object(ws, "_policy_docker_workspace", fake_policy):
        ws._docker_workspace_cache.clear()
        ws._docker_workspace_refcounts.clear()
        ws._docker_workspace_last_used.clear()
        ws._docker_workspace_locks.clear()
        try:
            _, key_a = await ws._acquire_docker_workspace(
                root=str(tmp_path), user_key="u1", skill_paths=["/s/a"]
            )
            _, key_b = await ws._acquire_docker_workspace(
                root=str(tmp_path), user_key="u1", skill_paths=["/s/b"]
            )
            # 同一集合再来一次：必须命中缓存，绝不重建容器
            _, key_a2 = await ws._acquire_docker_workspace(
                root=str(tmp_path), user_key="u1", skill_paths=["/s/a"]
            )
        finally:
            ws._docker_workspace_cache.clear()
            ws._docker_workspace_refcounts.clear()
            ws._docker_workspace_last_used.clear()
            ws._docker_workspace_locks.clear()

    assert key_a != key_b
    assert key_a == key_a2
    assert built == ["u1-" + ws._skill_paths_cache_token(["/s/a"]),
                     "u1-" + ws._skill_paths_cache_token(["/s/b"])], (
        "第二个技能集合不能复用第一个集合的容器"
    )


def test_sandbox_workspace_id_pattern_does_not_match_other_users():
    """按名字反查时不能用裸前缀匹配：``u1`` 不能吃掉 ``u1-b`` 的沙箱。"""
    import re

    pattern = ws._sandbox_workspace_id_pattern("u1")
    assert re.fullmatch(pattern, "u1")
    assert re.fullmatch(pattern, "u1-noskills")
    assert re.fullmatch(pattern, f"u1-{ws._skill_paths_cache_token(['/s/a'])}")
    assert not re.fullmatch(pattern, "u1-b")
    assert not re.fullmatch(pattern, "u1-b-abcdef123456")
    assert not re.fullmatch(pattern, "u2-abcdef123456")
    # 正则元字符必须被转义，否则用户名里的 ``.`` 会变成通配
    dotted = ws._sandbox_workspace_id_pattern("a.b")
    assert re.fullmatch(dotted, "a.b-noskills")
    assert not re.fullmatch(dotted, "axb-noskills")


def test_long_user_key_truncation_keeps_skill_token():
    """超长用户名不能把技能令牌挤出 63 字符的 Pod 名上限。

    K8s 的 ``_k8s_safe_name`` 只保留前 63 字符（合法化是 1:1 替换），若先拼令牌再
    截断，同一用户的多个技能集合会撞成同一个 Pod 名（第二个 Pod AlreadyExists）；
    截断用户键、保住令牌后，两者的 Pod 名必须不同且都 ≤63 字符。
    """
    long_key = "u" * 80 + "__1"
    tokens = [ws._skill_paths_cache_token([f"/s/{name}"]) for name in ("a", "b")]
    ids = [ws._sandbox_workspace_id(long_key, [f"/s/{name}"]) for name in ("a", "b")]
    pods = [ws._k8s_pod_name(item) for item in ids]

    assert ids[0] != ids[1]
    assert pods[0] != pods[1]
    assert all(len(pod) <= 63 for pod in pods)
    for token, pod in zip(tokens, pods):
        assert pod.endswith(token), "令牌必须落在 63 字符之内"
    # 反查模式要能覆盖截断形态（标签里存的就是截断后的 workspace_id）
    import re

    pattern = ws._sandbox_workspace_id_pattern(long_key)
    assert all(re.fullmatch(pattern, item) for item in ids)
    # 但普通用户的模式不会因为多列了截断形态而误配邻居
    short = ws._sandbox_workspace_id_pattern("u1")
    assert not re.fullmatch(short, "u1-b-abcdef123456")


@pytest.mark.asyncio
async def test_docker_container_lookup_uses_agentscope_labels(tmp_path):
    """容器名带令牌，只读入口必须按 AgentScope 的标签反查出真实在跑的那台。"""
    workdir = tmp_path / "ws"
    token = ws._skill_paths_cache_token(["/s/a"])

    class FakeContainer:
        def __init__(self, labels, name, created=0):
            self._container = {
                "Labels": labels,
                "Names": [f"/{name}"],
                "Created": created,
            }
            self.id = name

    class FakeContainers:
        def __init__(self):
            self.listed = [
                FakeContainer(
                    {
                        "agentscope.workspace": "true",
                        "agentscope.workspace.id": f"u1-{token}",
                    },
                    f"as_ws_u1-{token}",
                    created=100,
                ),
                FakeContainer(
                    {"agentscope.workspace.id": "u1-ffffffffffff"},
                    "as_ws_u1-ffffffffffff",
                    created=300,
                ),
                FakeContainer(
                    {"agentscope.workspace.id": "u2-abcdef123456"},
                    "as_ws_u2-abcdef123456",
                ),
                FakeContainer(
                    {"agentscope.workspace.id": "u1-b-abcdef123456"},
                    "as_ws_u1-b-abcdef123456",
                ),
                FakeContainer({"agentscope.workspace.id": f"u1-{token}"}, ""),
            ]

        async def list(self, **kwargs):
            assert kwargs.get("filters") == {"label": "agentscope.workspace=true"}
            return self.listed

    class FakeClient:
        def __init__(self):
            self.containers = FakeContainers()

    # 先放一个别的技能集合的缓存条目：它不是"第一个存在的容器"，但必须出现在候选里
    ws._docker_workspace_cache.clear()
    other = MagicMock()
    other._platform_workspace_id = "u1-othertoken00"
    ws._docker_workspace_cache[ws._docker_workspace_cache_key(str(workdir), "u1", ["/s/b"])] = other
    try:
        names = await ws._docker_sandbox_container_names(
            FakeClient(), user_key="u1", root=str(workdir)
        )
    finally:
        ws._docker_workspace_cache.clear()

    assert names[0] == "as_ws_u1-othertoken00", "进程内已知条目应排在最前"
    assert f"as_ws_u1-{token}" in names, "标签扫描必须能命中带令牌的真实容器"
    # 标签扫描命中多台时按创建时间倒序：最新那台才是当前技能集合的沙箱
    assert names.index("as_ws_u1-ffffffffffff") < names.index(f"as_ws_u1-{token}")
    assert "as_ws_u2-abcdef123456" not in names
    assert "as_ws_u1-b-abcdef123456" not in names, "前缀重合的其它用户不能被吃掉"
    assert names[-1] == "as_ws_u1", "历史无令牌命名作为兜底排在最后"
    # 标签里没有名字时用容器 id 兜底（containers.get 同样接受 id）
    assert f"as_ws_u1-{token}" in names


@pytest.mark.asyncio
async def test_docker_first_existing_container_falls_back_to_legacy_name(tmp_path):
    """老部署容器还叫 ``as_ws_<user>``：新名字 404 时必须继续找得到它。"""

    class FakeContainers:
        def __init__(self):
            self.asked: list[str] = []
            self.legacy = object()

        async def list(self, **kwargs):
            return []

        async def get(self, name):
            self.asked.append(name)
            if name == "as_ws_u1":
                return self.legacy
            error = RuntimeError("no such container")
            error.status = 404  # type: ignore[attr-defined]
            raise error

    class FakeClient:
        def __init__(self):
            self.containers = FakeContainers()

    client = FakeClient()
    container, name = await ws._docker_first_existing_container(client, user_key="u1")

    assert container is client.containers.legacy
    assert name == "as_ws_u1"
    # 没有进程内缓存、标签也扫不到任何容器时，只剩历史命名可试——不能凭空造名字
    assert client.containers.asked == ["as_ws_u1"]


@pytest.mark.asyncio
async def test_docker_first_existing_container_returns_none_when_absent():
    class FakeContainers:
        async def list(self, **kwargs):
            return []

        async def get(self, name):
            error = RuntimeError("gone")
            error.status = 404  # type: ignore[attr-defined]
            raise error

    class FakeClient:
        def __init__(self):
            self.containers = FakeContainers()

    container, name = await ws._docker_first_existing_container(FakeClient(), user_key="u1")
    assert container is None
    assert name == "as_ws_u1", "缺省返回首选名，便于错误信息里带出真实查找目标"


@pytest.mark.asyncio
async def test_docker_first_existing_container_prefers_label_match(tmp_path):
    """标签扫到带令牌的真实容器时，必须优先命中它而不是历史命名。"""

    class FakeContainers:
        def __init__(self):
            self.asked: list[str] = []
            self.found = object()

        async def list(self, **kwargs):
            token = ws._skill_paths_cache_token(["/s/a"])

            class Item:
                _container = {
                    "Labels": {"agentscope.workspace.id": f"u1-{token}"},
                    "Names": [f"/as_ws_u1-{token}"],
                }
                id = f"as_ws_u1-{token}"

            return [Item()]

        async def get(self, name):
            self.asked.append(name)
            if name.startswith("as_ws_u1-") and name != "as_ws_u1":
                return self.found
            error = RuntimeError("no such container")
            error.status = 404  # type: ignore[attr-defined]
            raise error

    class FakeClient:
        def __init__(self):
            self.containers = FakeContainers()

    client = FakeClient()
    container, name = await ws._docker_first_existing_container(client, user_key="u1")

    assert container is client.containers.found
    assert name == f"as_ws_u1-{ws._skill_paths_cache_token(['/s/a'])}"
    assert client.containers.asked == [name]


@pytest.mark.asyncio
async def test_seed_fingerprint_includes_skill_set_identity(env):
    """★ 核心回归：白名单变了（磁盘一个字节没动）也必须让指纹失效。"""
    workdir = env["workdir"]
    personal_a = env["personal"] / "mine-a"
    personal_b = env["personal"] / "mine-b"
    for path in (personal_a, personal_b):
        path.mkdir(parents=True, exist_ok=True)
        (path / "SKILL.md").write_text(
            "---\nname: mine\ndescription: d\n---\nbody\n", encoding="utf-8"
        )

    async def fake_forbidden():
        return set()

    with patch("app.services.ai.skills.policy.get_forbidden_skill_ids", fake_forbidden):
        fp_a = await ws._sandbox_skills_seed_fingerprint(str(workdir), [str(personal_a)])
        fp_a_again = await ws._sandbox_skills_seed_fingerprint(str(workdir), [str(personal_a)])
        fp_b = await ws._sandbox_skills_seed_fingerprint(str(workdir), [str(personal_b)])
        fp_none = await ws._sandbox_skills_seed_fingerprint(str(workdir), None)

    assert fp_a == fp_a_again, "同一技能集合必须得到稳定指纹，否则每次启动都重建"
    assert fp_a != fp_b, "技能集合变了指纹必须变，否则沙箱永远停留在旧副本"
    assert fp_a != fp_none
    # 显式传 layout 时不再从 skill_paths 推导（供已算好令牌的调用方复用）
    explicit = await ws._sandbox_skills_seed_fingerprint(
        str(workdir), None, ws._skill_paths_cache_token([str(personal_a)])
    )
    assert explicit == fp_a


def test_layout_scoped_manifest_and_fingerprint_files(tmp_path):
    """不同技能集合的账本/指纹必须各存一份，否则互相覆盖成"已是最新"。"""
    host_workdir = str(tmp_path / "agent_workspaces" / "u1")
    dir_a = ws._sandbox_skills_dir(host_workdir, "aaaa")
    dir_b = ws._sandbox_skills_dir(host_workdir, "bbbb")
    assert dir_a.endswith("sandbox/skills-aaaa")
    assert dir_b.endswith("sandbox/skills-bbbb")

    ws._write_sandbox_skill_manifest(host_workdir, ["alpha"], "aaaa")
    ws._write_sandbox_skill_manifest(host_workdir, ["beta"], "bbbb")
    assert ws._read_sandbox_skill_manifest(host_workdir, "aaaa") == {"alpha"}
    assert ws._read_sandbox_skill_manifest(host_workdir, "bbbb") == {"beta"}
    # 账本落在各自的技能目录里，不会被 AgentScope 当成技能条目
    assert Path(ws._sandbox_skill_manifest_path(host_workdir, "aaaa")).parent == Path(dir_a)

    ws._write_sandbox_skills_fingerprint(host_workdir, "fp-aaaa", "aaaa")
    assert ws._read_sandbox_skills_fingerprint(host_workdir, "aaaa") == "fp-aaaa"
    assert ws._read_sandbox_skills_fingerprint(host_workdir, "bbbb") is None
    # 指纹文件不进 skills 目录（避免被当成技能条目），按 layout 分文件
    assert ws._sandbox_skills_fingerprint_path(host_workdir, "aaaa").endswith(
        "sandbox/.public_skills_fingerprint-aaaa"
    )
    assert ws._sandbox_skills_fingerprint_path(host_workdir).endswith(
        "sandbox/.public_skills_fingerprint"
    )


def test_invalidation_and_commit_are_layout_scoped(tmp_path, monkeypatch):
    """作废 + 提交都必须落在**同一个** layout 目录上，否则指纹判定永远不一致。"""
    public = tmp_path / "public_skills"
    _write_skill(public, "pub-a")
    monkeypatch.setattr("app.utils.fs_access.get_platform_skills_root", lambda: str(public))
    host_workdir = str(tmp_path / "agent_workspaces" / "u1")

    seed_a = Path(ws._sandbox_skills_dir(host_workdir, "aaaa")) / ".seed"
    _write_skill(seed_a, "pub-a")
    seed_b = Path(ws._sandbox_skills_dir(host_workdir, "bbbb")) / ".seed"
    _write_skill(seed_b, "pub-a")

    invalidated, fingerprint = ws._invalidate_stale_sandbox_skill_seed(
        host_workdir, "fp-1", "aaaa"
    )
    assert invalidated is True
    assert not seed_a.exists()
    assert seed_b.exists(), "另一个技能集合的 .seed 不能被连带删除"

    _write_skill(seed_a, "pub-a")
    ws._commit_sandbox_skills_fingerprint(host_workdir, fingerprint, "aaaa")
    assert ws._read_sandbox_skills_fingerprint(host_workdir, "aaaa") == "fp-1"
    assert ws._read_sandbox_skills_fingerprint(host_workdir, "bbbb") is None
    assert not ws._invalidate_stale_sandbox_skill_seed(host_workdir, "fp-1", "aaaa")[0]


def test_legacy_skills_dir_is_migrated_once(tmp_path):
    """历史单份布局必须整体迁移，否则 agent 自建技能（在分区里）会凭空消失。"""
    host_workdir = str(tmp_path / "agent_workspaces" / "u1")
    legacy = Path(ws._sandbox_skills_dir(host_workdir))
    agent_skill = legacy / "default" / "agent-made"
    agent_skill.mkdir(parents=True)
    (agent_skill / "SKILL.md").write_text("agent made", encoding="utf-8")

    ws._migrate_legacy_sandbox_skills_dir(host_workdir, "aaaa")

    target = Path(ws._sandbox_skills_dir(host_workdir, "aaaa"))
    assert not legacy.exists()
    assert (target / "default" / "agent-made" / "SKILL.md").read_text(
        encoding="utf-8"
    ) == "agent made"
    # 幂等：已存在目标目录时不再动历史目录
    ws._migrate_legacy_sandbox_skills_dir(host_workdir, "aaaa")
    assert target.is_dir()


def test_legacy_skills_dir_is_kept_when_another_skill_set_uses_it(tmp_path):
    """已经存在其它技能集合的目录时，历史目录可能是别人正在用的，不能搬走。"""
    host_workdir = str(tmp_path / "agent_workspaces" / "u1")
    legacy = Path(ws._sandbox_skills_dir(host_workdir))
    (legacy / "default").mkdir(parents=True)
    other = Path(ws._sandbox_skills_dir(host_workdir, "bbbb"))
    other.mkdir(parents=True)

    ws._migrate_legacy_sandbox_skills_dir(host_workdir, "aaaa")

    assert legacy.is_dir(), "有兄弟目录时必须保守保留历史目录"
    assert not Path(ws._sandbox_skills_dir(host_workdir, "aaaa")).exists()


def test_partition_sync_stages_copies_and_reports_failures(env, monkeypatch):
    """同步失败要冒泡（否则会被记成"已是最新"而永久缺这个技能），且不破坏旧副本。"""
    import shutil as shutil_module

    skills_dir, seed = _seed_with(env, ["pub-a", "pub-b"])
    partition = skills_dir / "default"
    _write_skill(partition, "pub-a", "old body")
    ws._write_sandbox_skill_manifest(env["workdir"], ["pub-a"])

    real_copytree = shutil_module.copytree

    def flaky_copytree(src, dst, **kwargs):
        if str(src).endswith("pub-b"):
            raise OSError("disk full")
        return real_copytree(src, dst, **kwargs)

    monkeypatch.setattr(ws.shutil, "copytree", flaky_copytree)
    synced, failed = ws._sync_public_skills_into_sandbox_partitions(env["workdir"])

    assert failed == ["default/pub-b"]
    assert synced >= 1
    refreshed = (partition / "pub-a" / "SKILL.md").read_text(encoding="utf-8")
    assert "old body" not in refreshed, "成功的那一项必须已覆盖成新 seed 的内容"
    assert not (partition / "pub-b").exists()
    # 失败不留半成品 staging 目录
    assert [item.name for item in partition.iterdir() if item.name.startswith(".tmp-")] == []


def test_partition_sync_reports_undeletable_stale_skill(env, monkeypatch):
    """残留清不掉也必须算失败：否则指纹照样提交，脏技能永久留在分区里。"""
    skills_dir, _seed = _seed_with(env, ["pub-a"])
    partition = skills_dir / "default"
    _write_skill(partition, "pub-a")
    _write_skill(partition, "gone")  # 上一版装过、这一版已删除
    ws._write_sandbox_skill_manifest(env["workdir"], ["pub-a", "gone"])

    real_rmtree = ws.shutil.rmtree

    def refusing_rmtree(path, *args, **kwargs):
        if str(path).endswith("/gone") or str(path).endswith("\\gone"):
            raise PermissionError("read-only file system")
        return real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(ws.shutil, "rmtree", refusing_rmtree)
    _synced, failed = ws._sync_public_skills_into_sandbox_partitions(env["workdir"])

    assert failed == ["default/gone"], "清不掉的残留必须冒泡，让调用方跳过指纹提交"
    assert (partition / "gone").is_dir(), "函数不能假装删成功"


def test_k8s_pod_name_matches_agentscope_sanitizer():
    """Pod 名的算法必须与 AgentScope 逐字一致（否则状态/终端找不到 Pod）。"""
    from agentscope.workspace._k8s._constants import _k8s_safe_name

    for workspace_id in (
        "u1-noskills",
        "Alice__1-abcdef123456",
        "UPPER.Case",
        "x" * 200,
        "中文用户-abcdef123456",
    ):
        assert ws._k8s_pod_name(workspace_id) == _k8s_safe_name(workspace_id)


def test_prune_removed_session_skills_only_touches_ledger_entries(tmp_path):
    """来源**确实不存在**的会话副本必须删掉，但没登记过的目录（可能是别处放的）不能碰。"""
    seed_dir = tmp_path / "skills" / ".seed"
    for name in ("alpha", "beta", "untracked"):
        (seed_dir / name).mkdir(parents=True)
        (seed_dir / name / "SKILL.md").write_text("x", encoding="utf-8")
    source_root = tmp_path / "public_skills"
    _write_skill(source_root, "alpha")  # beta 的源已被删除；alpha 仍在
    skills = {
        "alpha": {"hash": "h1", "skill_name": "alpha", "skill_id": "alpha"},
        "beta": {"hash": "h2", "skill_name": "beta", "skill_id": "beta"},
        "legacy-entry": {"hash": "h3", "skill_name": "no-id"},
    }

    removed = ws._prune_removed_session_skills(
        str(seed_dir), skills, {"alpha"}, source_roots=[str(source_root)]
    )

    assert removed == ["beta"]
    assert (seed_dir / "alpha").is_dir()
    assert not (seed_dir / "beta").exists()
    assert (seed_dir / "untracked").is_dir(), "未登记的目录不属于本函数职责"
    assert set(skills) == {"alpha", "legacy-entry"}, "账本必须同步，否则下次播种会跳过复制"


def test_prune_removed_session_skills_keeps_narrowed_allowlist(tmp_path):
    """★ 契约：清理**不能**以「当前可用集合」为权威。

    同一会话里不同智能体各有自己的可用集合，智能体 B 的窄白名单播种不能删掉智能体 A
    铺下的技能；源目录暂时读不到（本次集合为空、或一个源根都不存在）时同样一律不动。
    """
    seed_dir = tmp_path / "skills" / ".seed"
    for name in ("alpha", "beta"):
        _write_skill(seed_dir, name)
    source_root = tmp_path / "public_skills"
    _write_skill(source_root, "alpha")
    _write_skill(source_root, "beta")

    def _fresh():
        return {
            "alpha": {"hash": "h1", "skill_name": "alpha", "skill_id": "alpha"},
            "beta": {"hash": "h2", "skill_name": "beta", "skill_id": "beta"},
        }

    # 窄白名单：beta 不在本次集合里，但它还在磁盘上 → 保留
    skills = _fresh()
    assert (
        ws._prune_removed_session_skills(
            str(seed_dir), skills, {"alpha"}, source_roots=[str(source_root)]
        )
        == []
    )
    assert set(skills) == {"alpha", "beta"}

    # 本次集合为空（整库暂时读不到）→ 一律不动
    skills = _fresh()
    assert (
        ws._prune_removed_session_skills(
            str(seed_dir), skills, set(), source_roots=[str(source_root)]
        )
        == []
    )
    assert set(skills) == {"alpha", "beta"}

    # 一个可读的源根都没有（volume 未挂载）→ 一律不动
    skills = _fresh()
    assert (
        ws._prune_removed_session_skills(
            str(seed_dir), skills, {"alpha"}, source_roots=[str(tmp_path / "not-mounted")]
        )
        == []
    )
    assert set(skills) == {"alpha", "beta"}

    # 个人技能源的历史 ``.seed`` 布局也算「源还在」
    personal_root = tmp_path / "personal_skills"
    _write_skill(personal_root / ws.SANDBOX_SKILL_SEED_DIR_NAME, "beta")
    skills = _fresh()
    assert (
        ws._prune_removed_session_skills(
            str(seed_dir),
            skills,
            {"alpha"},
            source_roots=[str(source_root), str(personal_root)],
        )
        == []
    )
    assert set(skills) == {"alpha", "beta"}


def test_host_prepare_lock_is_keyed_by_user_workspace(tmp_path):
    """用户级准备锁按宿主工作区路径分键：同一用户串行、不同用户互不阻塞。"""
    ws._sandbox_host_prepare_locks.clear()
    try:
        same_a = ws._sandbox_host_prepare_lock(str(tmp_path / "u1"))
        same_b = ws._sandbox_host_prepare_lock(str(tmp_path / "u1"))
        other = ws._sandbox_host_prepare_lock(str(tmp_path / "u2"))
        assert same_a is same_b
        assert same_a is not other
    finally:
        ws._sandbox_host_prepare_locks.clear()


# ---------------------------------------------------------------------------
# 「已禁用但沙箱里还能执行」的窗口：取用即核对 + 过期即逐出重建 + Bash 前状态核对
# ---------------------------------------------------------------------------


def test_idle_reap_defaults_are_fifteen_minutes():
    """沙箱空闲回收默认 15 分钟（更快释放「同一用户多技能集合」的多台容器/Pod）。"""
    assert ws.SANDBOX_IDLE_TIME_DEFAULT_MINUTES == 15
    assert ws.DOCKER_WORKSPACE_IDLE_SECONDS == 15 * 60
    assert ws.K8S_WORKSPACE_IDLE_SECONDS == 15 * 60
    from app.services import config_service

    assert config_service.SANDBOX_IDLE_TIME_DEFAULT == "15"


@pytest.mark.asyncio
async def test_effective_idle_seconds_falls_back_to_fifteen_minutes():
    """配置项缺失/非法时回退到 15 分钟；配了就按配置走。"""
    with patch(
        "app.services.config_service.ConfigService.get",
        AsyncMock(return_value=None),
    ):
        # reaper 循环传入的就是各自的模块常量，所以"配置缺失 → 15 分钟"成立
        assert (
            await ws._effective_sandbox_idle_seconds(
                default_seconds=ws.DOCKER_WORKSPACE_IDLE_SECONDS
            )
            == 900.0
        )
        assert (
            await ws._effective_sandbox_idle_seconds(
                default_seconds=ws.K8S_WORKSPACE_IDLE_SECONDS
            )
            == 900.0
        )
    with patch(
        "app.services.config_service.ConfigService.get",
        AsyncMock(return_value="45"),
    ):
        assert (
            await ws._effective_sandbox_idle_seconds(
                default_seconds=ws.DOCKER_WORKSPACE_IDLE_SECONDS
            )
            == 2700.0
        )


def test_parse_sandbox_cache_key_round_trips():
    """缓存键解析必须与算键函数严格对称（解析不出来就无法判定快照是否过期）。"""
    key = ws._docker_workspace_cache_key("/data", "u1", ["/s/a"])
    assert ws._parse_sandbox_cache_key(key) == (
        "/data",
        "u1",
        ws._skill_paths_cache_token(["/s/a"]),
        "docker",
    )
    # 工作区键只有 3 段，不能混进来
    assert ws._parse_sandbox_cache_key("/data/u1/sessions/c1::all::docker") is None


@pytest.mark.asyncio
async def test_snapshot_current_detects_skill_set_change(env):
    """★ 白名单/禁用集合变化 → 令牌变化 → 老快照必须判为过期。"""
    host_workdir = env["workdir"]
    layout_a = ws._skill_paths_cache_token([str(env["public"] / "pub-a")])
    root = str(Path(env["workdir"]).parent)
    key = ws._docker_workspace_cache_key(root, "u__1", [str(env["public"] / "pub-a")])
    with patch.object(
        ws, "_platform_public_skills_fingerprint", lambda: ws._dir_tree_fingerprint(str(env["public"]))
    ):
        os.makedirs(ws._sandbox_skills_dir(host_workdir, layout_a), exist_ok=True)
        (Path(ws._sandbox_skills_dir(host_workdir, layout_a)) / ws.SANDBOX_SKILL_SEED_DIR_NAME).mkdir(
            parents=True, exist_ok=True
        )
        current_fp = await ws._sandbox_skills_seed_fingerprint(
            host_workdir, [str(env["public"] / "pub-a")], layout_a
        )
        ws._write_sandbox_skills_fingerprint(host_workdir, current_fp, layout_a)

        # 令牌没变、内容也没变 → 仍是最新
        assert await ws._sandbox_skills_snapshot_is_current(
            key, skill_paths=[str(env["public"] / "pub-a")], forbidden_skill_ids=set()
        )
        # 该智能体的技能集合变成另一个 → 过期
        assert not await ws._sandbox_skills_snapshot_is_current(
            key, skill_paths=[str(env["public"] / "pub-a"), str(env["public"] / "pub-b")],
            forbidden_skill_ids=set(),
        )


@pytest.mark.asyncio
async def test_snapshot_current_detects_permission_change_with_same_layout(env):
    """★ 核心回归：令牌没变但禁用集合变了，老沙箱也必须判为过期。"""
    host_workdir = env["workdir"]
    paths = [str(env["public"] / "pub-a")]
    layout = ws._skill_paths_cache_token(paths)
    root = str(Path(env["workdir"]).parent)
    key = ws._docker_workspace_cache_key(root, "u__1", paths)
    with patch.object(
        ws, "_platform_public_skills_fingerprint", lambda: ws._dir_tree_fingerprint(str(env["public"]))
    ):
        seed_dir = Path(ws._sandbox_skills_dir(host_workdir, layout)) / ws.SANDBOX_SKILL_SEED_DIR_NAME
        seed_dir.mkdir(parents=True, exist_ok=True)
        (seed_dir / "dummy").write_text("x", encoding="utf-8")
        built_fp = await ws._sandbox_skills_seed_fingerprint(
            host_workdir, paths, layout, forbidden_skill_ids=set()
        )
        ws._write_sandbox_skills_fingerprint(host_workdir, built_fp, layout)

        assert await ws._sandbox_skills_snapshot_is_current(
            key, skill_paths=paths, forbidden_skill_ids=set()
        )
        assert not await ws._sandbox_skills_snapshot_is_current(
            key, skill_paths=paths, forbidden_skill_ids={"pub-a"}
        )


@pytest.mark.asyncio
async def test_snapshot_current_is_optimistic_when_unknown(env):
    """指纹读不到 / 公共库读不到时判为「最新」：不能因为判定不了就每轮重建容器。"""
    paths = [str(env["public"] / "pub-a")]
    root = str(Path(env["workdir"]).parent)
    key = ws._docker_workspace_cache_key(root, "u__1", paths)
    # 没有指纹文件
    assert await ws._sandbox_skills_snapshot_is_current(
        key, skill_paths=paths, forbidden_skill_ids=set()
    )
    # 公共技能库指纹不可用（返回 None）
    layout = ws._skill_paths_cache_token(paths)
    with patch.object(ws, "_platform_public_skills_fingerprint", lambda: None):
        ws._write_sandbox_skills_fingerprint(env["workdir"], "deadbeef", layout)
        assert await ws._sandbox_skills_snapshot_is_current(
            key, skill_paths=paths, forbidden_skill_ids=set()
        )
    # 非法键（测试替身）一律放行
    assert await ws._sandbox_skills_snapshot_is_current(
        "fake_cache_key", skill_paths=paths, forbidden_skill_ids=set()
    )


@pytest.mark.asyncio
async def test_create_workspace_evicts_stale_sandbox_on_cache_hit(tmp_path, monkeypatch):
    """★ 核心回归：缓存命中但快照过期时，必须逐出老沙箱并按当前技能集合重建。"""
    from app.services.ai.runtime.agentscope.workspace import (
        _docker_workspace_cache,
        _workspace_cache,
        _workspace_sandbox_refs,
        clear_workspace_cache,
        get_local_workspace,
    )

    monkeypatch.setattr(
        "app.services.config_service.ConfigService.get", AsyncMock(return_value="docker")
    )
    monkeypatch.setattr(
        "app.services.ai.runtime.agentscope.workspace.resolve_workspace_root",
        AsyncMock(return_value=str(tmp_path)),
    )
    monkeypatch.setattr(
        "app.services.ai.runtime.agentscope.workspace._prune_forbidden_session_skills",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "app.services.ai.skills.policy.get_forbidden_skill_ids", AsyncMock(return_value=set())
    )
    monkeypatch.setattr(
        ws, "discover_platform_skill_paths", lambda **kwargs: ["/public/skills/alpha"]
    )

    built: list[str] = []
    instances: list[Any] = []

    async def fake_acquire(*, root, user_key, skill_paths):
        key = ws._docker_workspace_cache_key(root, user_key, skill_paths)
        built.append(key)
        instance = MagicMock()
        instance.is_alive = True
        instance.close = AsyncMock()
        instances.append(instance)
        _docker_workspace_cache[key] = instance
        # 真实 acquire 会为该键建锁；逐出实现按锁存在与否决定是否关闭容器
        ws._docker_workspace_locks.setdefault(key, asyncio.Lock())
        return instance, key

    monkeypatch.setattr(ws, "_acquire_docker_workspace", fake_acquire)
    stale = AsyncMock(return_value=False)
    monkeypatch.setattr(ws, "_sandbox_skills_snapshot_is_current", stale)

    clear_workspace_cache()
    _docker_workspace_cache.clear()
    try:
        kwargs = dict(
            user_id="101",
            conversation_id="conv_stale",
            user_name="tester",
            user_info={"user_id": 101, "user_name": "tester"},
        )
        first = await get_local_workspace(**kwargs)
        assert first is not None
        assert len(built) == 1
        assert _workspace_sandbox_refs  # 会话已登记

        second = await get_local_workspace(**kwargs)
        assert second is not None
        # 过期 → 逐出（老容器被关掉）→ 重建，而不是把老沙箱原样交出去
        assert len(built) == 2, "快照过期时必须重建沙箱，不能命中老容器"
        assert stale.await_count >= 1
        assert instances[0].close.await_count == 1, "过期沙箱必须被真正关闭/删除"
        assert second[0] is not first[0], "重建后必须返回新的沙箱对象"
    finally:
        clear_workspace_cache()
        _docker_workspace_cache.clear()
        ws._docker_workspace_locks.clear()
        _workspace_cache.clear()
        _workspace_sandbox_refs.clear()


def test_conversation_workdir_matches_session_workdir(tmp_path):
    """只读入口自己拼的工作区路径必须与 resolve_session_workdir 完全一致。"""
    resolved = ws.resolve_session_workdir(
        root=str(tmp_path),
        user_id=101,
        conversation_id="conv/../weird id",
        user_name="tester",
    )
    user_key = ws.resolve_workspace_user_key(user_id=101, user_name="tester")
    assert ws._conversation_workdir(str(tmp_path), user_key, "conv/../weird id") == resolved


def test_find_cached_workspace_prefers_conversation_sandbox(tmp_path):
    """★ 同一用户多台沙箱时，状态/终端必须优先定位**该会话**在用的那一台。"""
    root = str(tmp_path)
    user_key = "tester__101"
    workdir = ws._conversation_workdir(root, user_key, "conv_a")
    other_workdir = ws._conversation_workdir(root, user_key, "conv_b")
    key_a = ws._docker_workspace_cache_key(root, user_key, ["/s/a"])
    key_b = ws._docker_workspace_cache_key(root, user_key, ["/s/b"])

    class FakeWs:
        def __init__(self, wid):
            self._platform_workspace_id = wid

    ws_a, ws_b = FakeWs("tester__101-tok-a"), FakeWs("tester__101-tok-b")
    ws._docker_workspace_cache[key_a] = ws_a
    ws._docker_workspace_cache[key_b] = ws_b
    ws._workspace_sandbox_refs[f"{workdir}::all::docker"] = key_a
    ws._workspace_sandbox_refs[f"{other_workdir}::all::docker"] = key_b
    try:
        assert (
            ws._find_cached_docker_workspace(root, user_key, conversation_id="conv_b") is ws_b
        ), "终端/状态必须进该会话自己的技能集合沙箱"
        assert (
            ws._find_cached_docker_workspace(root, user_key, conversation_id="conv_a") is ws_a
        )
        # 没有会话上下文时保持旧语义：返回该用户的某一台（不能报"没有沙箱"）
        assert ws._find_cached_docker_workspace(root, user_key) in (ws_a, ws_b)
        # 会话登记已失效（缓存对象被回收）也不能报"没有沙箱"
        assert (
            ws._find_cached_docker_workspace(root, user_key, conversation_id="conv_missing")
            in (ws_a, ws_b)
        )
    finally:
        ws._docker_workspace_cache.clear()
        ws._workspace_sandbox_refs.clear()


def test_long_user_keys_with_shared_prefix_get_distinct_sandbox_names():
    """★ 超长用户名不能因为"截断成同一前缀"而共用容器/Pod（Docker 互删 / Pod 撞名）。"""
    prefix = "very-long-sso-email-" + "x" * 40
    user_a = prefix + "-alice"
    user_b = prefix + "-bob"
    paths = ["/s/a"]
    id_a = ws._sandbox_workspace_id(user_a, paths)
    id_b = ws._sandbox_workspace_id(user_b, paths)
    assert id_a != id_b, "前缀相同的长用户名不能压成同一个沙箱身份"
    assert ws._k8s_pod_name(id_a) != ws._k8s_pod_name(id_b)
    assert len(ws._k8s_pod_name(id_a)) <= 63
    assert ws._k8s_pod_name(id_a).endswith(ws._skill_paths_cache_token(paths))

    import re

    pattern_a = ws._sandbox_workspace_id_pattern(user_a)
    assert re.fullmatch(pattern_a, id_a)
    assert not re.fullmatch(pattern_a, id_b), "反查模式不能把别人的沙箱算成自己的"


# ---------------------------------------------------------------------------
# 磁盘回收：已逐出沙箱的技能集合目录（白名单每变一次就多一份，此前只增不减）
# ---------------------------------------------------------------------------


def _build_layout_dir(host_workdir: str, layout: str, *, agent_skill: str | None = None):
    """造一个「平台铺好的」技能集合目录：``.seed`` + 账本 + 一个分区。"""
    skills_dir = Path(ws._sandbox_skills_dir(host_workdir, layout))
    seed = skills_dir / ws.SANDBOX_SKILL_SEED_DIR_NAME
    seed.mkdir(parents=True, exist_ok=True)
    (seed / "pub-a").mkdir(exist_ok=True)
    (seed / "pub-a" / "SKILL.md").write_text("body", encoding="utf-8")
    ws._write_sandbox_skill_manifest(host_workdir, ["pub-a"], layout)
    partition = skills_dir / "agent-1"
    partition.mkdir(exist_ok=True)
    (partition / "pub-a").mkdir(exist_ok=True)
    if agent_skill:
        (partition / agent_skill).mkdir(exist_ok=True)
    return skills_dir


def _age_dir(path: Path, seconds: float) -> None:
    stamp = time.time() - seconds
    os.utime(path, (stamp, stamp))


def test_collect_orphan_skills_dir_removes_disposable_layout(tmp_path):
    """★ 已逐出 + 无活跃条目 + 只有平台内容 → 目录应被回收（含指纹旁文件）。"""
    host_workdir = str(tmp_path / "u1")
    layout = ws._skill_paths_cache_token(["/s/a"])
    skills_dir = _build_layout_dir(host_workdir, layout)
    ws._write_sandbox_skills_fingerprint(host_workdir, "deadbeef", layout)
    _age_dir(skills_dir, ws.SANDBOX_SKILLS_DIR_MIN_AGE_SECONDS + 60)
    key = ws._docker_workspace_cache_key(str(tmp_path), "u1", ["/s/a"])
    try:
        assert ws.collect_orphan_sandbox_skills_dir(key) == str(skills_dir)
        assert not skills_dir.exists()
        assert ws._read_sandbox_skills_fingerprint(host_workdir, layout) is None
    finally:
        ws._docker_workspace_cache.clear()


def test_collect_orphan_skills_dir_keeps_live_and_agent_content(tmp_path):
    """三种情况都必须保留：还有活跃条目、含 agent 自建技能、目录太新。"""
    host_workdir = str(tmp_path / "u1")
    layout = ws._skill_paths_cache_token(["/s/a"])
    key = ws._docker_workspace_cache_key(str(tmp_path), "u1", ["/s/a"])
    try:
        # ① 进程内还有同一技能集合的活跃条目（别的会话正在用）
        skills_dir = _build_layout_dir(host_workdir, layout)
        _age_dir(skills_dir, ws.SANDBOX_SKILLS_DIR_MIN_AGE_SECONDS + 60)
        ws._docker_workspace_cache[key] = MagicMock()
        assert ws.collect_orphan_sandbox_skills_dir(key) is None
        assert skills_dir.exists()
        ws._docker_workspace_cache.clear()

        # ② 分区里有 agent 自建技能（删了就真丢数据）
        agent_dir = _build_layout_dir(host_workdir, layout, agent_skill="my-own-skill")
        _age_dir(agent_dir, ws.SANDBOX_SKILLS_DIR_MIN_AGE_SECONDS + 60)
        assert ws.collect_orphan_sandbox_skills_dir(key) is None
        assert (agent_dir / "agent-1" / "my-own-skill").is_dir()

        # ③ 刚建好的目录先留着，避免切换智能体时反复删了又建
        (agent_dir / "agent-1" / "my-own-skill").rmdir()
        _age_dir(agent_dir, 1)
        assert ws.collect_orphan_sandbox_skills_dir(key) is None
        assert agent_dir.exists()
    finally:
        ws._docker_workspace_cache.clear()


def test_collect_orphan_skills_dir_skips_legacy_and_unknown_keys(tmp_path):
    """历史单份布局 ``sandbox/skills`` 不归 GC 管；键格式不认识时也不动。"""
    host_workdir = str(tmp_path / "u1")
    legacy = Path(ws._sandbox_skills_dir(host_workdir, None))
    legacy.mkdir(parents=True)
    _age_dir(legacy, ws.SANDBOX_SKILLS_DIR_MIN_AGE_SECONDS + 60)
    assert ws.collect_orphan_sandbox_skills_dir("fake_cache_key") is None
    assert legacy.exists()


@pytest.mark.asyncio
async def test_evict_reclaims_skills_dir(tmp_path):
    """★ 逐出路径必须顺手回收目录（只在逐出成功后，失败/未逐出时不动）。"""
    host_workdir = str(tmp_path / "u1")
    layout = ws._skill_paths_cache_token(["/s/a"])
    skills_dir = _build_layout_dir(host_workdir, layout)
    _age_dir(skills_dir, ws.SANDBOX_SKILLS_DIR_MIN_AGE_SECONDS + 60)
    key = ws._docker_workspace_cache_key(str(tmp_path), "u1", ["/s/a"])
    instance = MagicMock()
    instance.close = AsyncMock()
    try:
        ws._docker_workspace_cache[key] = instance
        ws._docker_workspace_locks[key] = asyncio.Lock()
        ws._docker_workspace_refcounts[key] = 1
        ws._docker_workspace_last_used[key] = 0.0
        assert await ws._evict_docker_workspace_cache_entry(key, reason="test") == 1
        assert instance.close.await_count == 1
        assert not skills_dir.exists(), "容器已回收，孤立的技能集合目录也该回收"
    finally:
        ws._docker_workspace_cache.clear()
        ws._docker_workspace_locks.clear()
        ws._docker_workspace_refcounts.clear()
        ws._docker_workspace_last_used.clear()


def test_sandbox_skills_dir_is_disposable_matches_partition_sync_criteria(tmp_path):
    """可回收判据必须与分区同步一致：账本/当前 seed/公共名单内的都算平台内容。"""
    host_workdir = str(tmp_path / "u1")
    layout = ws._skill_paths_cache_token(["/s/a"])
    skills_dir = _build_layout_dir(host_workdir, layout)
    # 上一版账本里有、这一版 seed 里没有的（技能刚被删除）也算平台内容
    (skills_dir / "agent-1" / "pub-old").mkdir()
    ws._write_sandbox_skill_manifest(host_workdir, ["pub-a", "pub-old"], layout)
    assert ws._sandbox_skills_dir_is_disposable(host_workdir, layout)
    # 顶层出现非目录条目 → 不可判定，保留
    (skills_dir / "stray.txt").write_text("x", encoding="utf-8")
    assert not ws._sandbox_skills_dir_is_disposable(host_workdir, layout)
