"""删除技能（公共 / 个人）必须像重命名那样同步清理引用。

真实缺陷：``delete_entire_skill`` 只做 ``shutil.rmtree``，于是智能体白名单里留着已消失的
技能 ID、会话挂载里的 chip 指向不存在的技能、发布谱系里还挂着一条指向不存在平台技能的
「已发布」记录——全是静默断链。这组用例钉死「删除 = 目录消失 + 引用同步 + 如实回报」。
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from app.api.portal.endpoints import personal_skills, skills
from app.core.dependencies import require_api_key
from app.core.orm import get_db_session
from app.services.conversation_resource_service import TTL_SECONDS


pytestmark = pytest.mark.no_infrastructure


class _EmptyScalars:
    def all(self):
        return []

    def first(self):
        return None


class _EmptyResult:
    def scalars(self):
        return _EmptyScalars()

    def all(self):
        return []

    def first(self):
        return None


class _FakeDbSession:
    """只支持 execute/commit 的会话替身；查询一律返回空结果。"""

    def __init__(self):
        self.commits = 0

    async def execute(self, *_args, **_kwargs):
        return _EmptyResult()

    async def commit(self):
        self.commits += 1


class _FakeRedis:
    def __init__(self, store):
        self.store = store
        self.ttls = []

    async def scan(self, cursor=0, match=None, count=200):
        return 0, list(self.store.keys())

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ex=None):
        self.store[key] = value
        self.ttls.append(ex)


async def _fake_admin():
    return {"user_id": 1, "user_name": "admin", "role": "admin"}


async def _fake_db():
    yield _FakeDbSession()


def _build_app() -> FastAPI:
    portal = APIRouter()
    portal.include_router(personal_skills.router, prefix="/skills/personal")
    portal.include_router(skills.router, prefix="/skills")
    app = FastAPI()
    app.dependency_overrides[require_api_key] = _fake_admin
    app.dependency_overrides[skills.skill_platform_admin] = _fake_admin
    app.dependency_overrides[get_db_session] = _fake_db
    app.include_router(portal, prefix="/api/portal")
    return app


def _conversation_key(user_id: int = 1) -> str:
    return f"conversation:{user_id}:conv-1:resource_scope_v1"


@pytest.fixture
def global_skills_dir(tmp_path):
    skill_dir = tmp_path / "demo-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("---\nname: demo\n---\n\n# body\n", encoding="utf-8")
    with patch(
        "app.api.portal.endpoints.skills.settings", SimpleNamespace(SKILLS_DIR=str(tmp_path))
    ):
        yield tmp_path


def test_delete_platform_skill_syncs_agent_and_conversation_references(global_skills_dir):
    store = {
        _conversation_key(): json.dumps(
            {
                "project_name": "p",
                "skills": [{"id": "demo-skill", "scope": "global"}, {"id": "keep", "scope": "global"}],
            }
        )
    }
    redis = _FakeRedis(store)

    with patch(
        "app.services.conversation_resource_service.get_redis",
        new_callable=AsyncMock,
        return_value=redis,
    ):
        response = TestClient(_build_app()).delete("/api/portal/skills/demo-skill")

    assert response.status_code == 200, response.text
    body = response.json()
    assert "物理彻底移除" in body["message"]
    assert not (global_skills_dir / "demo-skill").exists(), "目录必须真的被删掉"
    # 三处引用都要出现在 synced 里（这里的 DB 查询返回空，所以数量是 0/[]，但链路必须跑到）
    assert set(body["data"]["synced"]) == {"agents", "publications", "conversations"}
    assert body["data"]["synced"]["conversations"] == 1
    assert body["data"]["warnings"] == []

    scope = json.loads(store[_conversation_key()])
    assert [item["id"] for item in scope["skills"]] == ["keep"]
    assert scope["project_name"] == "p", "改写挂载列表不能顺手丢掉范围里的其它字段"
    assert redis.ttls == [TTL_SECONDS], "清理挂载也必须带原来那 30 天 TTL"


def test_delete_platform_skill_is_not_silent_when_sync_fails(global_skills_dir):
    """引用同步失败/Redis 不可用必须写进 warnings，而不是静默成功。"""
    with patch(
        "app.services.conversation_resource_service.get_redis",
        new_callable=AsyncMock,
        side_effect=RuntimeError("redis down"),
    ), patch(
        "app.services.skill_rename_service.remove_agent_skill_bindings",
        new=AsyncMock(side_effect=RuntimeError("db down")),
    ), patch(
        "app.services.skill_publication_service.mark_platform_skill_publications_revoked",
        new=AsyncMock(side_effect=RuntimeError("db down")),
    ):
        response = TestClient(_build_app()).delete("/api/portal/skills/demo-skill")

    assert response.status_code == 200, response.text
    warnings = response.json()["data"]["warnings"]
    assert len(warnings) == 3, warnings
    assert not (global_skills_dir / "demo-skill").exists()


def test_delete_platform_skill_404s_when_missing(global_skills_dir):
    response = TestClient(_build_app()).delete("/api/portal/skills/not-there")
    assert response.status_code == 404


def test_delete_personal_skill_removes_personal_mount(tmp_path):
    personal_dir = tmp_path / "personal"
    skill_dir = personal_dir / "demo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: demo\n---\n", encoding="utf-8")
    store = {
        _conversation_key(): json.dumps({"skills": [{"id": "demo", "scope": "personal"}]})
    }
    redis = _FakeRedis(store)

    with patch(
        "app.api.portal.endpoints.personal_skills.get_user_personal_skills_dir",
        return_value=str(personal_dir),
    ), patch(
        "app.services.conversation_resource_service.get_redis",
        new_callable=AsyncMock,
        return_value=redis,
    ):
        response = TestClient(_build_app()).delete("/api/portal/skills/personal/demo")

    assert response.status_code == 200, response.text
    assert not skill_dir.exists()
    assert response.json()["data"]["synced"]["conversations"] == 1
    assert json.loads(store[_conversation_key()])["skills"] == []
    assert redis.ttls == [TTL_SECONDS]


def test_delete_personal_skill_warns_when_platform_copy_still_published(tmp_path):
    """删除个人副本不会下架平台技能：必须明确告诉用户去哪里下架。"""
    personal_dir = tmp_path / "personal"
    skill_dir = personal_dir / "demo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: demo\n---\n", encoding="utf-8")

    with patch(
        "app.api.portal.endpoints.personal_skills.get_user_personal_skills_dir",
        return_value=str(personal_dir),
    ), patch(
        "app.services.conversation_resource_service.get_redis",
        new_callable=AsyncMock,
        return_value=_FakeRedis({}),
    ), patch(
        "app.services.skill_publication_service.list_active_platform_skills_for_personal_skill",
        new=AsyncMock(return_value=["public-demo-12345678"]),
    ):
        response = TestClient(_build_app()).delete("/api/portal/skills/personal/demo")

    assert response.status_code == 200, response.text
    warnings = response.json()["data"]["warnings"]
    assert len(warnings) == 1
    assert "public-demo-12345678" in warnings[0]
    assert "下架" in warnings[0]
