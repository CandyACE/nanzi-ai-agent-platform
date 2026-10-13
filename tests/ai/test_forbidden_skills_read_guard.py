"""禁用公共技能：读判定收口（原生 Read/Glob/Grep 与 /api/v1/chat/fs 共用同一套判定）。

修复前的缺口：``SKILLS_DIR`` 整体在公共可读根里（``fs_access.get_public_fs_roots``），
于是"禁用"只拦住了注入层，被禁技能的 ``SKILL.md`` 用原生文件工具或文件浏览器接口照样读得到。

这里的判定口径：
- 平台技能根（``settings.SKILLS_DIR``）下的**第一段目录名就是技能 id**（见
  ``skill_resolver._scan_skill_dir`` 用目录名解析 Frontmatter），只做精确同名比较，
  不做前缀匹配——``alpha_1`` / 非 ASCII 名字不会被 ``alpha`` 误伤；
- 会话快照目录（用户工作区 ``skills/``）的目录名是 ``sanitize(SKILL.md 的 name)``，
  与技能 id 无关，因此不参与本判定；
- 拿不到禁用集合（未预热 / 已过期 / 查询异常）一律放行（fail-open），
  管理员与个人技能完全不受影响。
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, PropertyMock, patch

import pytest

from app.services.ai.skills import policy as skill_policy
from app.services.ai.tools.resource_catalog_tools import list_accessible_directories
from app.utils import fs_access


pytestmark = pytest.mark.no_infrastructure

USER_INFO = {"u_id_val": 1, "id": 1, "user_id": 1, "user_name": "alice", "role": "user"}
ADMIN_INFO = {"u_id_val": 1, "id": 1, "user_id": 1, "user_name": "alice", "role": "admin"}


@pytest.fixture(autouse=True)
def _clean_sync_cache():
    """同步读缓存是进程内状态：用例之间必须互不污染。"""
    skill_policy.clear_forbidden_skill_cache()
    yield
    skill_policy.clear_forbidden_skill_cache()


def _write_skill(root: Path, skill_id: str, *, name: str | None = None) -> Path:
    skill_dir = root / skill_id
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name or skill_id}\ndescription: 演示 {skill_id}\n---\n\n# {skill_id}\n",
        encoding="utf-8",
    )
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir(exist_ok=True)
    (scripts_dir / "run.py").write_text("print('ok')\n", encoding="utf-8")
    return skill_dir


@pytest.fixture()
def skills_root(tmp_path):
    """平台技能根：常规 id、带 `_1` 后缀的近似名、非 ASCII 名各一份。"""
    root = tmp_path / "platform-skills"
    for skill_id in ("alpha", "beta", "gamma", "alpha_1", "数据分析", "数据分析_1"):
        _write_skill(root, skill_id)

    # settings.SKILLS_DIR 是属性：patch 它同时覆盖 get_platform_skills_root() 与技能扫描
    with patch("app.core.config.Settings.SKILLS_DIR", new_callable=PropertyMock) as mock_dir:
        mock_dir.return_value = str(root)
        yield root


def _fake_session():
    class _FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    return _FakeSession()


def _permission_patch(forbidden_skills, *, roles=None):
    perms = SimpleNamespace(
        roles=set(roles or {"user"}),
        permissions=SimpleNamespace(forbidden_skills=list(forbidden_skills)),
    )
    service = AsyncMock()
    service.get_user_permissions = AsyncMock(return_value=perms)
    return patch("app.services.permission_service.PermissionService", return_value=service)


# --------------------------------------------------------------------------- #
# 1. 目录名 vs 技能 id
# --------------------------------------------------------------------------- #


def test_platform_skill_directory_name_is_the_skill_id(skills_root):
    """判定依据：平台技能根下第一段目录名就是技能 id（注入器/提示词也按这个 id 拼路径）。"""
    assert (
        fs_access.resolve_platform_skill_id_for_path(str(skills_root / "alpha" / "SKILL.md"))
        == "alpha"
    )
    assert (
        fs_access.resolve_platform_skill_id_for_path(str(skills_root / "alpha" / "scripts" / "run.py"))
        == "alpha"
    )
    assert fs_access.resolve_platform_skill_id_for_path(str(skills_root / "alpha")) == "alpha"
    # 技能根本身不属于任何技能（列目录仍然要能用）
    assert fs_access.resolve_platform_skill_id_for_path(str(skills_root)) is None


def test_session_snapshot_directories_are_not_treated_as_skill_ids(tmp_path, skills_root):
    """会话快照目录名是 sanitize(SKILL.md 的 name)（还可能是 name_1），与技能 id 无关。

    它位于用户工作区的 skills/ 下，不在平台技能根下，所以不会被"按技能 id 拒绝"的判定命中；
    那批残留由 workspace 侧按内容哈希清理（见 _prune_stale_session_skills）。
    """
    from app.services.ai.runtime.agentscope.workspace import _sanitize_skill_dir_name

    snapshot_dir_name = _sanitize_skill_dir_name("数据分析 / 报表")
    snapshot_path = (
        tmp_path / "agent_workspaces" / "alice__1" / "sessions" / "conv-1" / "skills"
        / snapshot_dir_name / "SKILL.md"
    )
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text("# snapshot\n", encoding="utf-8")

    assert fs_access.resolve_platform_skill_id_for_path(str(snapshot_path)) is None


def test_lookalike_directory_names_are_not_misjudged(skills_root):
    """前缀 / 非 ASCII 名字：只有**精确同名**的目录才被禁，近似名照旧可读。"""
    skill_policy.remember_forbidden_skill_ids(1, {"alpha", "数据分析"})

    assert (
        fs_access.resolve_platform_skill_id_for_path(str(skills_root / "alpha_1" / "SKILL.md"))
        == "alpha_1"
    )
    assert fs_access.is_runtime_path_allowed(str(skills_root / "alpha_1" / "SKILL.md"), USER_INFO)
    assert fs_access.is_runtime_path_allowed(
        str(skills_root / "数据分析_1" / "SKILL.md"), USER_INFO
    )
    assert not fs_access.is_runtime_path_allowed(str(skills_root / "alpha" / "SKILL.md"), USER_INFO)
    assert not fs_access.is_runtime_path_allowed(
        str(skills_root / "数据分析" / "SKILL.md"), USER_INFO
    )


# --------------------------------------------------------------------------- #
# 2. 读判定：被禁拒绝、未禁放行
# --------------------------------------------------------------------------- #


def test_forbidden_skill_dir_is_denied_on_every_read_path(skills_root):
    skill_policy.remember_forbidden_skill_ids(1, {"gamma"})
    forbidden_skill_md = str(skills_root / "gamma" / "SKILL.md")

    # 原生文件工具（Read/Glob/Grep 走 is_runtime_path_allowed）
    assert fs_access.is_runtime_path_allowed(forbidden_skill_md, USER_INFO) is False
    assert fs_access.is_runtime_path_allowed(str(skills_root / "gamma"), USER_INFO) is False
    assert fs_access.is_runtime_path_allowed(str(skills_root / "gamma" / "scripts" / "run.py"), USER_INFO) is False
    # 文件浏览器接口（/api/v1/chat/fs/* 走 is_path_allowed）
    assert fs_access.is_path_allowed(forbidden_skill_md, USER_INFO) is False
    assert fs_access.is_path_allowed(str(skills_root / "gamma"), USER_INFO) is False
    with pytest.raises(Exception):
        fs_access.assert_path_allowed(forbidden_skill_md, USER_INFO)


def test_not_forbidden_skills_stay_readable(skills_root):
    """反向断言：没有一刀切——未禁技能的正文、脚本、技能根本身都还要能读。"""
    skill_policy.remember_forbidden_skill_ids(1, {"gamma"})

    assert fs_access.is_path_allowed(str(skills_root / "alpha" / "SKILL.md"), USER_INFO) is True
    assert fs_access.is_runtime_path_allowed(str(skills_root / "alpha" / "SKILL.md"), USER_INFO) is True
    assert (
        fs_access.is_runtime_path_allowed(
            str(skills_root / "alpha" / "scripts" / "run.py"), USER_INFO
        )
        is True
    )
    assert fs_access.is_runtime_path_allowed(str(skills_root), USER_INFO) is True
    assert fs_access.is_runtime_path_allowed(str(skills_root / "beta" / "SKILL.md"), USER_INFO) is True


def test_admin_is_unaffected(skills_root):
    skill_policy.remember_forbidden_skill_ids(1, {"gamma"})
    forbidden_skill_md = str(skills_root / "gamma" / "SKILL.md")

    # 生产布局里平台技能根就在 data 根下，这里把可读根一并指过去以模拟真实布局
    with patch.object(fs_access, "get_allowed_fs_roots", lambda _info: [str(skills_root)]):
        assert fs_access.is_forbidden_platform_skill_path(forbidden_skill_md, ADMIN_INFO) is False
        assert fs_access.is_runtime_path_allowed(forbidden_skill_md, ADMIN_INFO) is True
        assert fs_access.is_path_allowed(forbidden_skill_md, ADMIN_INFO) is True
        assert fs_access.assert_path_allowed(forbidden_skill_md, ADMIN_INFO) == forbidden_skill_md


def test_same_named_personal_skill_is_unaffected(skills_root):
    """个人技能目录不在平台技能根下：同名也不受禁用影响（禁的是平台发布的那一份）。"""
    skill_policy.remember_forbidden_skill_ids(1, {"gamma"})

    personal_root = os.path.join(
        fs_access.get_data_base_dir(), "agent_workspaces", "alice__1"
    )
    personal_skill_md = os.path.join(personal_root, "skills", "gamma", "SKILL.md")

    with patch.object(fs_access, "get_user_private_workspace_root", lambda _info: personal_root):
        assert fs_access.resolve_platform_skill_id_for_path(personal_skill_md) is None
        assert fs_access.is_forbidden_platform_skill_path(personal_skill_md, USER_INFO) is False
        assert fs_access.is_path_allowed(personal_skill_md, USER_INFO) is True
        assert fs_access.is_runtime_path_allowed(personal_skill_md, USER_INFO) is True


# --------------------------------------------------------------------------- #
# 3. 拿不到禁用集合时 fail-open + 日志
# --------------------------------------------------------------------------- #


def test_cache_miss_fails_open_with_a_log(skills_root, caplog):
    with caplog.at_level(logging.DEBUG, logger="app.services.ai.skills.policy"):
        assert fs_access.is_runtime_path_allowed(str(skills_root / "gamma" / "SKILL.md"), USER_INFO)

    assert any("read-cache miss" in record.getMessage() for record in caplog.records)


def test_expired_cache_fails_open(skills_root):
    skill_policy.remember_forbidden_skill_ids(1, {"gamma"})
    assert fs_access.is_runtime_path_allowed(str(skills_root / "gamma" / "SKILL.md"), USER_INFO) is False

    with patch.object(skill_policy, "FORBIDDEN_SKILL_CACHE_TTL_SECONDS", -1.0):
        assert skill_policy.get_cached_forbidden_skill_ids(1) is None
        assert fs_access.is_runtime_path_allowed(str(skills_root / "gamma" / "SKILL.md"), USER_INFO)


@pytest.mark.asyncio
async def test_query_failure_logs_and_never_fails_closed_globally(skills_root, caplog):
    """查询异常 + 冷缓存 → 放行（与修复前一致），且留 ERROR 日志。"""
    with patch("app.core.orm.AsyncSessionLocal", side_effect=RuntimeError("db down")), caplog.at_level(
        logging.ERROR, logger="app.services.ai.skills.policy"
    ):
        assert await skill_policy.get_forbidden_skill_ids(1) == set()

    assert any(
        "Failed to resolve forbidden skills" in record.getMessage() for record in caplog.records
    )
    # 失败不写缓存：未命中 → 放行，且下一轮会真实重试
    assert skill_policy.get_cached_forbidden_skill_ids(1) is None
    assert fs_access.is_runtime_path_allowed(str(skills_root / "gamma" / "SKILL.md"), USER_INFO)


@pytest.mark.asyncio
async def test_failed_refresh_keeps_the_last_known_set(skills_root):
    """已经拿到过的禁用集合不会因为一次查询失败就被清空。

    这是刻意的取舍：若失败即写空集合，那么"让权限查询失败"就成了一条自我解禁的路径。
    失败只保留旧值（最多活到 TTL 到期），冷缓存才走"未命中即放行"。
    """
    with patch("app.core.orm.AsyncSessionLocal", return_value=_fake_session()), _permission_patch(
        ["gamma"]
    ):
        await skill_policy.get_forbidden_skill_ids(1)

    with patch("app.core.orm.AsyncSessionLocal", side_effect=RuntimeError("db down")):
        await skill_policy.get_forbidden_skill_ids(1)

    assert skill_policy.get_cached_forbidden_skill_ids(1) == frozenset({"gamma"})
    assert fs_access.is_runtime_path_allowed(str(skills_root / "gamma" / "SKILL.md"), USER_INFO) is False


# --------------------------------------------------------------------------- #
# 4. 缓存写入 / 预热接线
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_async_query_primes_the_sync_cache():
    with patch("app.core.orm.AsyncSessionLocal", return_value=_fake_session()), _permission_patch(
        ["gamma", "beta"]
    ):
        assert await skill_policy.get_forbidden_skill_ids(1) == {"gamma", "beta"}

    assert skill_policy.get_cached_forbidden_skill_ids("1") == frozenset({"gamma", "beta"})
    assert skill_policy.is_platform_skill_id_forbidden("gamma", USER_INFO) is True
    assert skill_policy.is_platform_skill_id_forbidden("alpha", USER_INFO) is False


@pytest.mark.asyncio
async def test_priming_is_throttled_but_forced_when_asked():
    with patch("app.core.orm.AsyncSessionLocal", return_value=_fake_session()), _permission_patch(
        ["gamma"]
    ) as service_patch:
        await skill_policy.prime_forbidden_skill_cache(1, max_age_seconds=0)
        await skill_policy.prime_forbidden_skill_cache(1)  # 节流窗口内：复用缓存
        await skill_policy.prime_forbidden_skill_cache(1, max_age_seconds=0)

    assert service_patch.return_value.get_user_permissions.await_count == 2


def test_every_sync_boundary_primes_the_cache():
    """同步判定只能读缓存，所以每个"判定边界"都必须先预热（源码级接线契约）。"""
    agent_service = Path("app/services/ai/agent_service.py").read_text(encoding="utf-8")
    assert "prime_forbidden_skill_cache(required_user_id, max_age_seconds=0)" in agent_service

    fs_endpoint = Path("app/api/v1/endpoints/fs.py").read_text(encoding="utf-8")
    assert "router = APIRouter(dependencies=[Depends(_prime_forbidden_skill_cache)])" in fs_endpoint

    workspace = Path("app/services/ai/runtime/agentscope/workspace.py").read_text(encoding="utf-8")
    assert "await self._refresh_forbidden_skill_cache()" in workspace
    assert "prime_forbidden_skill_cache(user_info=self._user_info)" in workspace


# --------------------------------------------------------------------------- #
# 5. 目录清单不再把被禁技能列为可读
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_directory_catalog_hides_forbidden_skills(skills_root, monkeypatch):
    monkeypatch.setattr(
        "app.services.ai.skills.policy.get_forbidden_skill_ids",
        AsyncMock(return_value={"gamma"}),
    )
    mock_ctx = SimpleNamespace(
        user_id=1,
        is_admin=False,
        conversation_id="conv-1",
        user_dimensions={"username": "alice"},
    )

    with (
        patch(
            "app.services.ai.tools.resource_catalog_tools.get_current_agent_context",
            return_value=mock_ctx,
        ),
        patch("app.services.config_service.ConfigService.get", AsyncMock(return_value="local")),
    ):
        raw = await list_accessible_directories.ainvoke({})

    data = json.loads(raw)
    skills_entry = {
        item["directory_name"]: item for item in data["public_directories"]["directories"]
    }["skills"]

    assert "gamma" not in skills_entry["available_skill_ids"]
    assert "alpha" in skills_entry["available_skill_ids"]
    assert skills_entry["forbidden_skill_ids"] == ["gamma"]
    assert "已被管理员禁用" in skills_entry["description"]


@pytest.mark.asyncio
async def test_directory_catalog_lists_everything_when_nothing_is_forbidden(skills_root, monkeypatch):
    monkeypatch.setattr(
        "app.services.ai.skills.policy.get_forbidden_skill_ids", AsyncMock(return_value=set())
    )
    mock_ctx = SimpleNamespace(
        user_id=1,
        is_admin=False,
        conversation_id="conv-1",
        user_dimensions={"username": "alice"},
    )

    with (
        patch(
            "app.services.ai.tools.resource_catalog_tools.get_current_agent_context",
            return_value=mock_ctx,
        ),
        patch("app.services.config_service.ConfigService.get", AsyncMock(return_value="local")),
    ):
        raw = await list_accessible_directories.ainvoke({})

    skills_entry = {
        item["directory_name"]: item
        for item in json.loads(raw)["public_directories"]["directories"]
    }["skills"]

    assert {"alpha", "beta", "gamma"} <= set(skills_entry["available_skill_ids"])
    assert skills_entry["forbidden_skill_ids"] == []
    assert "已被管理员禁用" not in skills_entry["description"]
