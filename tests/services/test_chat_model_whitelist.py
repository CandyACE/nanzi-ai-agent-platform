"""聊天模型白名单：权限数据通道与唯一判据函数。

关键语义（与 element:/menu: 相反）：**未配置 = 不限制**。
因此判据函数返回 None 表示不限制，返回非空 set 表示白名单。
"""

import pytest


pytestmark = pytest.mark.no_infrastructure


def test_permission_set_has_models_field_with_default_empty():
    from app.schemas.permission import PermissionSet

    assert PermissionSet().models == []
    assert PermissionSet(models=["gpt-4o"]).models == ["gpt-4o"]


def test_permission_set_detail_has_models_field():
    from app.schemas.permission import PermissionSetDetail

    assert PermissionSetDetail().models == []


def test_aggregate_collects_model_resource_type():
    from app.models.permission import ResourcePermission
    from app.schemas.permission import PermissionSet
    from app.services.permission_service import PermissionService

    service = PermissionService.__new__(PermissionService)
    perm_set = PermissionSet()
    service._aggregate_permissions(
        perm_set,
        [
            ResourcePermission(resource_type="model", resource_id="gpt-4o"),
            ResourcePermission(resource_type="model", resource_id="deepseek-chat"),
            ResourcePermission(resource_type="element", resource_id="element:user:edit"),
        ],
    )

    assert sorted(perm_set.models) == ["deepseek-chat", "gpt-4o"]
    assert perm_set.elements == ["element:user:edit"]


def test_empty_whitelist_means_unrestricted():
    from app.services.permission_service import PermissionService

    assert PermissionService._resolve_allowed_model_ids("user", []) is None


def test_admin_is_unrestricted():
    from app.services.permission_service import PermissionService

    assert PermissionService._resolve_allowed_model_ids("admin", ["gpt-4o"]) is None


def test_whitelist_returns_deduplicated_set():
    from app.services.permission_service import PermissionService

    result = PermissionService._resolve_allowed_model_ids(
        "user", ["gpt-4o", "gpt-4o", "deepseek-chat"]
    )

    assert result == {"gpt-4o", "deepseek-chat"}


class _FakeScalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None

    def scalars(self):
        return _FakeScalars(self._rows)


class _QueuedSession:
    """按调用顺序返回预设结果：第一次查角色，第二次查 model 权限行。"""

    def __init__(self, results):
        self._results = list(results)

    async def execute(self, _stmt):
        return _FakeResult(self._results.pop(0))


async def test_allowed_model_ids_queries_role_and_model_rows():
    from app.services.permission_service import PermissionService

    session = _QueuedSession([["user"], ["gpt-4o", "deepseek-chat"]])
    service = PermissionService(session)

    assert await service.get_chat_allowed_model_ids(7) == {"gpt-4o", "deepseek-chat"}


async def test_allowed_model_ids_returns_none_when_no_rows():
    from app.services.permission_service import PermissionService

    session = _QueuedSession([["user"], []])
    service = PermissionService(session)

    assert await service.get_chat_allowed_model_ids(7) is None


async def test_allowed_model_ids_returns_none_for_admin():
    from app.services.permission_service import PermissionService

    session = _QueuedSession([["admin"]])
    service = PermissionService(session)

    assert await service.get_chat_allowed_model_ids(7) is None


def test_cached_permission_key_bumped_to_v4():
    source = open("app/services/permission_service.py", encoding="utf-8").read()

    assert "sys:auth:permissions:v4:user:" in source
    assert "sys:auth:permissions:v3:user:" not in source


def test_update_paths_include_model_resource_type_and_respect_explicit_clear():
    source = open("app/services/permission_service.py", encoding="utf-8").read()

    # 两个写入方法都要处理 model，否则保存权限会静默清空白名单
    assert source.count('"models" in updates.model_fields_set') >= 2
    assert source.count('resource_type="model", resource_id=str(model_id)') >= 2
