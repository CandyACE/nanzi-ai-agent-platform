"""模型列表的聊天作用域过滤：只有 scope=chat 才按白名单收窄。"""

import pytest


pytestmark = pytest.mark.no_infrastructure


class _Scalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return _Scalars(self._rows)


class _CapturingSession:
    """记录被执行的语句，供 SQL 断言。"""

    def __init__(self, rows):
        self.rows = rows
        self.statements = []

    async def execute(self, stmt):
        self.statements.append(stmt)
        return _Result(self.rows)


class _FakeModel:
    def __init__(self, model_id):
        from datetime import datetime

        self.id = "id-1"
        self.model_id = model_id
        self.name = model_id
        self.type = "llm"
        self.provider = "openai"
        self.is_active = True
        self.thinking_enable = False
        self.thinking_only = False
        self.allow_disable_thinking = True
        self.created_at = datetime(2026, 1, 1)
        self.updated_at = datetime(2026, 1, 1)


async def test_scope_chat_applies_whitelist_filter(monkeypatch):
    from app.api.portal.endpoints import models as models_module
    from app.services.permission_service import PermissionService

    async def _fake_allowed(self, user_id):
        return {"gpt-4o"}

    monkeypatch.setattr(PermissionService, "get_chat_allowed_model_ids", _fake_allowed)
    session = _CapturingSession([_FakeModel("gpt-4o")])

    await models_module.list_models(
        type=None, include_inactive=False, scope="chat",
        db=session, user={"id": 7, "role": "user"},
    )

    sql = str(session.statements[0].compile(compile_kwargs={"literal_binds": True}))
    assert "model_id IN ('gpt-4o')" in sql


async def test_scope_chat_without_whitelist_does_not_filter(monkeypatch):
    from app.api.portal.endpoints import models as models_module
    from app.services.permission_service import PermissionService

    async def _fake_allowed(self, user_id):
        return None

    monkeypatch.setattr(PermissionService, "get_chat_allowed_model_ids", _fake_allowed)
    session = _CapturingSession([_FakeModel("anything")])

    await models_module.list_models(
        type=None, include_inactive=False, scope="chat",
        db=session, user={"id": 7, "role": "user"},
    )

    sql = str(session.statements[0].compile(compile_kwargs={"literal_binds": True}))
    assert "model_id IN" not in sql


async def test_scope_chat_admin_is_not_filtered(monkeypatch):
    from app.api.portal.endpoints import models as models_module
    from app.services.permission_service import PermissionService

    async def _explode(self, user_id):  # 管理员不查白名单
        raise AssertionError("admin should not query whitelist")

    monkeypatch.setattr(PermissionService, "get_chat_allowed_model_ids", _explode)
    session = _CapturingSession([_FakeModel("anything")])

    await models_module.list_models(
        type=None, include_inactive=False, scope="chat",
        db=session, user={"id": 7, "role": "admin"},
    )

    sql = str(session.statements[0].compile(compile_kwargs={"literal_binds": True}))
    assert "model_id IN" not in sql


async def test_default_scope_stays_full_list(monkeypatch):
    from app.api.portal.endpoints import models as models_module
    from app.services.permission_service import PermissionService

    async def _explode(self, user_id):  # 不带 scope 时不应该查白名单
        raise AssertionError("should not query whitelist without scope=chat")

    monkeypatch.setattr(PermissionService, "get_chat_allowed_model_ids", _explode)
    session = _CapturingSession([_FakeModel("anything")])

    await models_module.list_models(
        type=None, include_inactive=False, db=session, user={"id": 7, "role": "user"},
    )

    sql = str(session.statements[0].compile(compile_kwargs={"literal_binds": True}))
    assert "model_id IN" not in sql
