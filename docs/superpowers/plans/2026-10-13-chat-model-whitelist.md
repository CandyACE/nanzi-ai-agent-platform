# 聊天输入框模型白名单 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让角色级 / 用户级「聊天可用模型」白名单限制输入框可手动切换的模型，未配置白名单的人行为完全不变。

**Architecture:** 复用 `ai_agent_resource_permissions`（`resource_type='model'`）承载白名单，角色与用户取并集；判据收敛为 `PermissionService.get_chat_allowed_model_ids()`（`None` = 不限制）；聊天端点过滤 `?scope=chat` 候选，并在 `debug_options` 清洗段拒绝越权的显式覆盖（智能体默认模型豁免）；输入框候选 = 白名单 ∪ 智能体默认模型，去重后 ≤1 个则隐藏。

**Tech Stack:** FastAPI + SQLAlchemy 2.x async + Pydantic 2（后端）；Vue 3 + TypeScript + Tailwind（前端）；pytest / `pytest --confcutdir=tests/frontend` / node transpile harness（测试）。

**Spec:** [docs/superpowers/specs/2026-10-13-chat-model-whitelist-design.md](../specs/2026-10-13-chat-model-whitelist-design.md)

> **仓库约束（必须遵守）**
> - 按 `AGENTS.md`：**Agent 不执行 `git commit`**。每个任务末尾的提交命令只作为交付说明，由用户自行执行。
> - 数据库变更只能新增迁移 SQL；本计划**不需要任何迁移**。
> - 不运行 `./dev.sh`、部署脚本或数据库操作。

---

## 文件结构

**Create**
| 文件 | 职责 |
| --- | --- |
| `tests/services/test_chat_model_whitelist.py` | 判据函数与权限聚合/读写的后端行为测试 |
| `tests/api/portal/test_models_scope_chat.py` | `?scope=chat` 过滤接口的行为与契约测试 |
| `tests/services/test_published_agent_model_name.py` | 智能体默认模型查询助手的测试 |
| `tests/api/v1/test_chat_model_override_whitelist.py` | 端点层越权拦截的完整行为矩阵 |
| `tests/frontend/test_chat_model_whitelist_behavior.py` | 输入框候选决策纯函数的 node harness 测试 |
| `tests/frontend/test_chat_model_whitelist_contract.py` | 前端接线契约（权限资源页、EmbedChat、API 方法） |

**Modify**
| 文件 | 改动 |
| --- | --- |
| `app/schemas/permission.py` | `PermissionSet.models` / `PermissionSetDetail.models` |
| `app/services/permission_service.py` | 聚合分支、读写分支（含 `model_fields_set` 守卫）、判据函数与纯函数、展示名、缓存键 v4 |
| `app/api/portal/endpoints/models.py` | `list_models` 支持 `scope=chat` |
| `app/services/ai/agent_manager.py` | 新增 `published_agent_model_name()` |
| `app/api/v1/endpoints/chat.py` | `_enforce_chat_model_whitelist()` + 在清洗段调用 |
| `frontend/src/api/model.ts` | `listAvailableForChat()` |
| `frontend/src/utils/modelSelect.ts` | `resolveChatModelSwitch()` 纯函数 |
| `frontend/src/views/Roles.vue` | 权限弹窗「可用模型」资源页 |
| `frontend/src/views/Users.vue` | 同上 |
| `frontend/src/views/EmbedChat.vue` | 候选并集接线 + 越权提示 |
| `tests/CHECKLIST.md` | 交付记录 |

---

## Task 1: 权限数据通道（schema / 聚合 / 读写 / 判据函数 / 缓存键）

**Files:**
- Modify: `app/schemas/permission.py`
- Modify: `app/services/permission_service.py`
- Test: `tests/services/test_chat_model_whitelist.py`（新建）

- [ ] **Step 1: 写失败测试**

新建 `tests/services/test_chat_model_whitelist.py`：

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest -q tests/services/test_chat_model_whitelist.py`
Expected: FAIL —— `ImportError: cannot import name 'PermissionSet'` 不成立（模块存在），实际失败点为 `AssertionError`（`PermissionSet().models` 不存在）与 `AttributeError: _resolve_allowed_model_ids`。

- [ ] **Step 3: 实现**

`app/schemas/permission.py` —— `PermissionSet` 增加字段（放在 `forbidden_commands` 之后）：

```python
    models: List[str] = Field(
        default_factory=list,
        description="聊天可手动切换的模型 ID 白名单（空 = 不限制，与 element 语义相反）",
    )
```

同文件 `PermissionSetDetail` 增加：

```python
    models: List[ResourceDetail] = Field(default_factory=list)
```

`app/services/permission_service.py`：

1) 缓存键升版本（`_get_cache_key`）：

```python
    async def _get_cache_key(self, user_id: int) -> str:
        # v4: 新增 models（聊天模型白名单）；旧缓存缺该字段会解析成空列表 = 不限制，
        # 会让「刚配好的白名单不生效」难以排查，这里强制回源。
        return f"sys:auth:permissions:v4:user:{user_id}"
```

2) `_aggregate_permissions`（约 552 行）在 `forbidden_command` 分支后追加：

```python
        elif p.resource_type == "model":
            # 白名单：空 = 不限制（消费端用 _resolve_allowed_model_ids 统一判定）
            perm_set.models.append(p.resource_id)
```

3) 新增纯函数与判据函数（放在 `_aggregate_permissions` 之后）：

```python
    @staticmethod
    def _resolve_allowed_model_ids(user_role: str, model_ids: list[str]) -> Optional[set[str]]:
        """白名单唯一判据：None = 不限制。

        与 element:/menu: 的「列出才有权限」相反——未配置（含并集为空）表示不限制。
        管理员直通，避免管理员把自己锁在门外。
        """
        if str(user_role or "").strip() == "admin":
            return None
        normalized = {str(model_id).strip() for model_id in model_ids if str(model_id).strip()}
        return normalized or None

    async def get_chat_allowed_model_ids(self, user_id) -> Optional[set[str]]:
        """返回该用户聊天可手动切换的模型集合；None 表示不限制（未配置）。"""
        try:
            parsed_uid = int(user_id)
        except (TypeError, ValueError):
            parsed_uid = user_id

        role_stmt = select(User.role).where(User.id == parsed_uid)
        user_role = (await self.db.execute(role_stmt)).scalar_one_or_none()
        if str(user_role or "").strip() == "admin":
            return None

        model_stmt = (
            select(distinct(ResourcePermission.resource_id))
            .outerjoin(
                UserRoleRelation,
                ResourcePermission.role_id == UserRoleRelation.role_id,
            )
            .where(
                ResourcePermission.enabled == True,  # noqa: E712 - 与文件内既有写法一致
                ResourcePermission.resource_type == "model",
                or_(
                    ResourcePermission.user_id == parsed_uid,
                    UserRoleRelation.user_id == parsed_uid,
                ),
            )
        )
        rows = (await self.db.execute(model_stmt)).scalars().all()
        return self._resolve_allowed_model_ids(user_role, list(rows))
```

同时确认文件顶部导入包含 `or_`（若无则把 `from sqlalchemy import select, delete, distinct` 改为 `from sqlalchemy import select, delete, distinct, or_`），并确保 `User` 已导入（该文件已在 `get_user_permissions` 中使用 `User`）。

4) `_fetch_permission_details`（约 255 行）为 model 补展示名——在该函数 `return details` 之前插入（名字缺失时回退 `model_id`）：

```python
        if perm_set.models:
            model_stmt = select(AIModel.model_id, AIModel.name).where(
                AIModel.model_id.in_(perm_set.models)
            )
            for model_id, model_name in (await self.db.execute(model_stmt)).all():
                label = str(model_name or model_id)
                details.models.append(
                    ResourceDetail(id=str(model_id), name=label, display_name=label)
                )
```

（需要在文件顶部补 `from app.models.ai_model import AIModel`。）

5) `update_user_permissions` 与 `update_role_permissions`（约 579 / 659 行）——两处都要：

```python
            types_to_update = ["agent", "dataset", "api", "metadata", "menu", "element", "forbidden_tool", "forbidden_command"]
            # 未显式提交 models（旧客户端）时不触碰 model 记录，避免静默清空白名单
            if "models" in updates.model_fields_set:
                types_to_update = [*types_to_update, "model"]
```

以及写入段（两处各自使用 `user_id=` / `role_id=`）：

```python
            for model_id in (updates.models if "models" in updates.model_fields_set else []):
                new_perms.append(
                    ResourcePermission(
                        user_id=user_id, resource_type="model", resource_id=str(model_id)
                    )
                )
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest -q tests/services/test_chat_model_whitelist.py`
Expected: PASS（13 项）

同时跑权限相关的既有回归：
Run: `.venv/bin/python -m pytest -q tests/services -k "permission"`
Expected: PASS

- [ ] **Step 5: 交付（由用户提交）**

```bash
# 由用户执行（Agent 不自动 commit）
git add app/schemas/permission.py app/services/permission_service.py tests/services/test_chat_model_whitelist.py
git commit -m "feat(permission): 聊天模型白名单数据通道与唯一判据（空 = 不限制）"
```

---

## Task 2: 过滤接口 `GET /api/portal/models?scope=chat`

**Files:**
- Modify: `app/api/portal/endpoints/models.py:66-81`
- Test: `tests/api/portal/test_models_scope_chat.py`（新建）

- [ ] **Step 1: 写失败测试**

```python
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
        self.id = 1
        self.model_id = model_id
        self.name = model_id
        self.type = "llm"
        self.is_active = True


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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest -q tests/api/portal/test_models_scope_chat.py`
Expected: FAIL —— `TypeError: list_models() got an unexpected keyword argument 'scope'`

- [ ] **Step 3: 实现**

`app/api/portal/endpoints/models.py` 的 `list_models`：

```python
@router.get("", response_model=List[AIModelResponse])
async def list_models(
    type: str = None,
    include_inactive: bool = False,
    scope: str = None,
    db: AsyncSession = Depends(get_db_session),
    user: Dict = Depends(get_current_user)
):
    """List all AI models.

    scope=chat：聊天输入框专用，按当前用户的模型白名单收窄（未配置白名单 = 不限制）。
    不传 scope 的管理端调用保持全量，因此版本配置候选 / 系统配置页 / 模型管理页不受影响。
    """
    query = select(AIModel)
    if not include_inactive:
        query = query.where(AIModel.is_active == True)
    if type:
        query = query.where(AIModel.type == type)

    if scope == "chat" and str(user.get("role") or "") != "admin":
        from app.services.permission_service import PermissionService

        allowed_model_ids = await PermissionService(db).get_chat_allowed_model_ids(user.get("id"))
        if allowed_model_ids is not None:
            query = query.where(AIModel.model_id.in_(sorted(allowed_model_ids)))

    result = await db.execute(query)
    return [AIModelResponse.from_orm_custom(m) for m in result.scalars().all()]
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest -q tests/api/portal/test_models_scope_chat.py`
Expected: PASS（3 项）

- [ ] **Step 5: 交付（由用户提交）**

```bash
# 由用户执行
git add app/api/portal/endpoints/models.py tests/api/portal/test_models_scope_chat.py
git commit -m "feat(models): 新增 scope=chat 按模型白名单收窄候选，管理端调用保持全量"
```

---

## Task 3: 越权拦截（端点层）与智能体默认模型豁免

**Files:**
- Modify: `app/services/ai/agent_manager.py`（新增 `published_agent_model_name`）
- Modify: `app/api/v1/endpoints/chat.py`（新增 `_enforce_chat_model_whitelist` 并在清洗段调用）
- Test: `tests/services/test_published_agent_model_name.py`、`tests/api/v1/test_chat_model_override_whitelist.py`（均新建）

- [ ] **Step 1: 写失败测试**

`tests/services/test_published_agent_model_name.py`：

```python
"""按智能体取「已发布版本」的编排模型名：查不到/异常一律返回空串。"""

import pytest

pytestmark = pytest.mark.no_infrastructure


class _Result:
    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row


class _Session:
    def __init__(self, row):
        self._row = row

    async def execute(self, _stmt):
        return _Result(self._row)


async def test_returns_published_version_model_name():
    from app.services.ai.agent_manager import AgentManagerService

    assert await AgentManagerService.published_agent_model_name(
        _Session(("gpt-4o",)), "agent-1"
    ) == "gpt-4o"


async def test_returns_empty_when_no_version():
    from app.services.ai.agent_manager import AgentManagerService

    assert await AgentManagerService.published_agent_model_name(_Session(None), "agent-1") == ""


async def test_returns_empty_without_agent_id():
    from app.services.ai.agent_manager import AgentManagerService

    assert await AgentManagerService.published_agent_model_name(_Session(("gpt-4o",)), None) == ""


async def test_degrades_to_empty_on_failure():
    from app.services.ai.agent_manager import AgentManagerService

    class _Broken:
        async def execute(self, _stmt):
            raise RuntimeError("boom")

    assert await AgentManagerService.published_agent_model_name(_Broken(), "agent-1") == ""
```

`tests/api/v1/test_chat_model_override_whitelist.py`：

```python
"""输入端模型覆盖的白名单拦截：未配置放行 / 白名单内放行 / 默认模型豁免 / 越权 403。"""

import pytest
from fastapi import HTTPException

pytestmark = pytest.mark.no_infrastructure


class _Session:
    """不查库：白名单与默认模型都由 monkeypatch 提供。"""

    async def execute(self, _stmt):  # pragma: no cover - 正常路径不会走到
        raise AssertionError("unexpected query")


async def _call(monkeypatch, *, role="user", allowed={"gpt-4o"}, default="deepseek-chat", model="gpt-4o"):
    from app.api.v1.endpoints import chat as chat_module
    from app.services.permission_service import PermissionService

    async def _fake_allowed(self, user_id):
        return allowed

    async def _fake_default(session, agent_id, version_id=None):
        return default

    monkeypatch.setattr(PermissionService, "get_chat_allowed_model_ids", _fake_allowed)
    monkeypatch.setattr(
        chat_module.AgentManagerService, "published_agent_model_name", _fake_default
    )
    await chat_module._enforce_chat_model_whitelist(
        db=_Session(),
        user_info={"id": 7, "role": role},
        chat_user_id=7,
        effective_debug_options={"model": model},
        agent_id="agent-1",
        version_id=None,
    )


async def test_allows_model_in_whitelist(monkeypatch):
    await _call(monkeypatch, model="gpt-4o")


async def test_allows_agent_default_model_outside_whitelist(monkeypatch):
    await _call(monkeypatch, allowed={"gpt-4o"}, default="deepseek-chat", model="deepseek-chat")


async def test_rejects_model_outside_whitelist(monkeypatch):
    with pytest.raises(HTTPException) as excinfo:
        await _call(monkeypatch, allowed={"gpt-4o"}, default="deepseek-chat", model="gpt-4-turbo")

    assert excinfo.value.status_code == 403
    assert "可用范围" in excinfo.value.detail


async def test_unconfigured_whitelist_allows_everything(monkeypatch):
    await _call(monkeypatch, allowed=None, model="whatever")


async def test_empty_override_is_ignored(monkeypatch):
    await _call(monkeypatch, allowed=set(), model="")


async def test_admin_bypasses_whitelist(monkeypatch):
    await _call(monkeypatch, role="admin", allowed={"gpt-4o"}, model="gpt-4-turbo")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest -q tests/services/test_published_agent_model_name.py tests/api/v1/test_chat_model_override_whitelist.py`
Expected: FAIL —— `AttributeError: type object 'AgentManagerService' has no attribute 'published_agent_model_name'`（先修 Task 3 的助手，再跑第二个文件）。

- [ ] **Step 3: 实现**

`app/services/ai/agent_manager.py`（与 `get_version_config` 相邻处新增）：

```python
    @staticmethod
    async def published_agent_model_name(
        session: AsyncSession,
        agent_id: Optional[str],
        version_id: Optional[str] = None,
    ) -> str:
        """返回该智能体「已发布版本」配置的编排模型名；查不到返回空串。

        仅供模型白名单的豁免判断使用：白名单限制用户手动切换，但不能连智能体
        自己指定的模型都拦掉。异常一律降级为空串（宁可少豁免，不影响主流程）。
        """
        if not agent_id:
            return ""
        try:
            if version_id:
                stmt = select(AIAgentVersion.model_name).where(AIAgentVersion.id == version_id)
            else:
                stmt = (
                    select(AIAgentVersion.model_name)
                    .where(
                        AIAgentVersion.agent_id == agent_id,
                        AIAgentVersion.status == "PUBLISHED",
                    )
                    .order_by(AIAgentVersion.version_number.desc())
                    .limit(1)
                )
            row = (await session.execute(stmt)).first()
            return str(row[0] or "").strip() if row else ""
        except Exception as exc:  # noqa: BLE001 - 豁免查询失败不应阻断聊天
            logger.warning("Failed to resolve published model for agent %s: %s", agent_id, exc)
            return ""
```

（`AIAgentVersion.status == "PUBLISHED"` 的具体枚举值与字段名以 `attach_published_model_switch_flags` 中既有查询为准，实现时照抄该处写法；`select` / `logger` / `AsyncSession` / `Optional` 该文件已导入。）

`app/api/v1/endpoints/chat.py` 新增模块级函数（放在 `create_chat_completion` 之前）：

```python
async def _enforce_chat_model_whitelist(
    *,
    db: AsyncSession,
    user_info: Dict[str, Any],
    chat_user_id: Any,
    effective_debug_options: Dict[str, Any],
    agent_id: Optional[str],
    version_id: Optional[str],
) -> None:
    """只约束客户端显式注入的模型覆盖；未配置白名单（None）= 不限制。

    智能体版本指定的模型天然豁免：用户「选回默认模型」必须始终合法。
    """
    override_model = str(effective_debug_options.get("model") or "").strip()
    if not override_model or str(user_info.get("role") or "") == "admin":
        return

    from app.services.permission_service import PermissionService

    allowed_model_ids = await PermissionService(db).get_chat_allowed_model_ids(chat_user_id)
    if allowed_model_ids is None:
        return

    agent_default_model = await AgentManagerService.published_agent_model_name(
        db, agent_id, version_id
    )
    if agent_default_model:
        allowed_model_ids = allowed_model_ids | {agent_default_model}

    if override_model not in allowed_model_ids:
        logger.warning(
            "chat model override rejected: user=%s model=%s agent=%s",
            chat_user_id, override_model, agent_id,
        )
        raise HTTPException(
            status_code=403,
            detail="该模型不在你的可用范围内，请联系管理员调整",
        )
```


> **踩坑记录（实测）**：新增的 `_enforce_chat_model_whitelist` 必须放在 `@router.post("/completions", …)` **装饰器之前**。第一次插入时放在了装饰器与 `async def create_chat_completion` 之间，FastAPI 把守卫函数当成了路由处理函数，启动时报 `Invalid args for response field! ... AsyncSession is a valid Pydantic field type`。

并在 `effective_debug_options` 清洗段落末尾调用：

```python
    await _enforce_chat_model_whitelist(
        db=db,
        user_info=user_info,
        chat_user_id=chat_user_id,
        effective_debug_options=effective_debug_options,
        agent_id=completion_request.agent_id,
        version_id=completion_request.version_id,
    )
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest -q tests/services/test_published_agent_model_name.py tests/api/v1/test_chat_model_override_whitelist.py`
Expected: PASS（10 项）

- [ ] **Step 5: 交付（由用户提交）**

```bash
# 由用户执行
git add app/services/ai/agent_manager.py app/api/v1/endpoints/chat.py \
        tests/services/test_published_agent_model_name.py tests/api/v1/test_chat_model_override_whitelist.py
git commit -m "feat(chat): 端点层拦截白名单外的模型覆盖，智能体默认模型豁免"
```

---

## Task 4: 前端 API 与权限弹窗「可用模型」资源页

**Files:**
- Modify: `frontend/src/api/model.ts:101-103`
- Modify: `frontend/src/views/Roles.vue`（`permissionData` 约 1309 行、资源页模板、`savePermissions` 约 2152 行）
- Modify: `frontend/src/views/Users.vue`（同构位置）
- Test: `tests/frontend/test_chat_model_whitelist_contract.py`（新建）

- [ ] **Step 1: 写失败测试**

```python
"""前端接线契约：聊天作用域 API、权限弹窗「可用模型」资源页、未配置=不限制文案。"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODEL_API = (ROOT / "frontend/src/api/model.ts").read_text(encoding="utf-8")
ROLES = (ROOT / "frontend/src/views/Roles.vue").read_text(encoding="utf-8")
USERS = (ROOT / "frontend/src/views/Users.vue").read_text(encoding="utf-8")


def test_model_api_exposes_chat_scoped_listing():
    assert "listAvailableForChat" in MODEL_API
    assert "scope: 'chat'" in MODEL_API
    # 管理端语义不能被改动
    assert "list: (type?: string, includeInactive = false)" in MODEL_API


def test_permission_dialogs_have_model_whitelist_page():
    for source in (ROLES, USERS):
        assert "models: []" in source
        assert "可用模型" in source
        assert "未配置 = 不限制" in source


def test_saving_permissions_sends_models_array():
    for source in (ROLES, USERS):
        assert "models:" in source
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest -q tests/frontend/test_chat_model_whitelist_contract.py`
Expected: FAIL —— `assert 'listAvailableForChat' in MODEL_API`

- [ ] **Step 3: 实现**

`frontend/src/api/model.ts` 在 `list` 之后新增：

```ts
  /** 聊天输入框专用：后端按当前用户的模型白名单收窄（未配置 = 全量）。 */
  listAvailableForChat: () => {
    return axios.get<AIModel[]>('/api/portal/models', { params: { scope: 'chat' } })
  },
```

`Roles.vue` 与 `Users.vue` 各自：

1) `permissionData` 声明与初始值增加 `models: string[]` / `models: []`。
2) 资源页 Tab 增加「可用模型」项（沿用该文件既有的资源 Tab 结构，`activeResTab` 增加 `'models'`），列表按现有资源项渲染方式遍历 `availableModels`（`llm | multimodal` 且 `is_active`，已选但停用的保留并标注「已停用」）。
3) 资源页顶部说明文案：`未配置 = 不限制；配置后只能在勾选的模型（与其角色白名单取并集）中手动切换。`
4) 加载已选：把 `permissions.models` 写入 `permissionData.models`；保存：`models: permissionData.value.models` 一并提交（字段名必须与后端 `PermissionUpdate.models` 一致）。

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest -q tests/frontend/test_chat_model_whitelist_contract.py`
Expected: PASS（3 项）

类型检查：
Run: `cd frontend && node --max-old-space-size=6144 ./node_modules/vue-tsc/bin/vue-tsc.js --noEmit -p tsconfig.app.json`
Expected: 与改动前基线相比**零新增错误**（基线见 `/tmp/vuetsc-before.log`）。

- [ ] **Step 5: 交付（由用户提交）**

```bash
# 由用户执行
git add frontend/src/api/model.ts frontend/src/views/Roles.vue frontend/src/views/Users.vue \
        tests/frontend/test_chat_model_whitelist_contract.py
git commit -m "feat(ui): 角色/用户权限弹窗新增「可用模型」资源页与 scope=chat 拉取"
```

---

## Task 5: 输入框候选 = 白名单 ∪ 智能体默认模型

**Files:**
- Modify: `frontend/src/utils/modelSelect.ts`
- Modify: `frontend/src/views/EmbedChat.vue`（`fetchModels` 约 7599 行、`manualModelSwitchAllowed` 约 2910 行、模型切换器 props 约 1353 行）
- Test: `tests/frontend/test_chat_model_whitelist_behavior.py`（新建，node harness）

- [ ] **Step 1: 写失败测试**

```python
"""输入框候选决策纯函数：版本开关 × 白名单 × 智能体默认模型。

候选 = 白名单（后端 scope=chat 已过滤） ∪ 智能体默认模型，去重后 ≤1 个则隐藏；
并集为空时给提示而不是静默消失。
"""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UTILS = ROOT / "frontend/src/utils/modelSelect.ts"

HARNESS = r"""
const ts = require('typescript');
const fs = require('fs');
const src = fs.readFileSync(process.argv[2], 'utf8');
const js = ts.transpileModule(src, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText;
const module_ = { exports: {} };
new Function('exports', 'require', 'module', js)(module_.exports, require, module_);
const { resolveChatModelSwitch } = module_.exports;
const input = JSON.parse(process.argv[3]);
process.stdout.write(JSON.stringify(resolveChatModelSwitch(input)));
"""


def _decide(**kwargs):
    payload = {
        "versionAllowsSwitch": True,
        "chatModels": [],
        "agentDefaultModel": "",
        **kwargs,
    }
    result = subprocess.run(
        ["node", "-e", HARNESS, str(UTILS), json.dumps(payload)],
        capture_output=True, text=True, check=True,
    )
    return json.loads(result.stdout)


def _models(*ids):
    return [{"model_id": mid, "name": f"{mid}-名称", "type": "llm", "is_active": True} for mid in ids]


def test_version_forbids_switch_hides_control():
    assert _decide(versionAllowsSwitch=False, chatModels=_models("a"))["visible"] is False


def test_unconfigured_whitelist_returns_all_candidates():
    decision = _decide(chatModels=_models("a", "b", "c"))
    assert decision["visible"] is True
    assert [o["value"] for o in decision["options"]] == ["a", "b", "c"]


def test_whitelist_is_unioned_with_agent_default_model():
    decision = _decide(chatModels=_models("b", "c"), agentDefaultModel="a")
    assert [o["value"] for o in decision["options"]] == ["a", "b", "c"]
    assert decision["options"][0]["isAgentDefault"] is True


def test_single_candidate_after_dedupe_hides_control():
    decision = _decide(chatModels=_models("a"), agentDefaultModel="a")
    assert decision["visible"] is False


def test_two_candidates_keep_control_visible():
    decision = _decide(chatModels=_models("b"), agentDefaultModel="a")
    assert decision["visible"] is True
    assert [o["value"] for o in decision["options"]] == ["a", "b"]


def test_empty_union_shows_hint_instead_of_disappearing():
    decision = _decide(chatModels=[], agentDefaultModel="")
    assert decision["visible"] is False
    assert "停用" in decision["emptyHint"] or "管理员" in decision["emptyHint"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest -q tests/frontend/test_chat_model_whitelist_behavior.py`
Expected: FAIL —— `TypeError: resolveChatModelSwitch is not a function`

- [ ] **Step 3: 实现**

`frontend/src/utils/modelSelect.ts` 追加：

```ts
export interface ChatModelSwitchInput {
  versionAllowsSwitch: boolean
  chatModels: SelectableModel[]
  agentDefaultModel: string
}

export interface ChatModelSwitchDecision {
  visible: boolean
  options: (ModelSelectOption & { isAgentDefault?: boolean })[]
  emptyHint: string
}

const CHAT_MODEL_EMPTY_HINT = '你的可用模型已全部停用，请联系管理员'

/** 输入框候选 = 白名单候选（后端 scope=chat 已过滤） ∪ 智能体默认模型。 */
export function resolveChatModelSwitch(input: ChatModelSwitchInput): ChatModelSwitchDecision {
  if (!input.versionAllowsSwitch) {
    return { visible: false, options: [], emptyHint: '' }
  }

  const options: (ModelSelectOption & { isAgentDefault?: boolean })[] = []
  const seen = new Set<string>()
  const defaultModel = (input.agentDefaultModel || '').trim()

  if (defaultModel) {
    const matched = input.chatModels.find((model) => model.model_id === defaultModel)
    options.push({
      value: defaultModel,
      label: `${matched ? modelOptionLabel(matched) : defaultModel} · 智能体默认`,
      isAgentDefault: true,
    })
    seen.add(defaultModel)
  }

  for (const model of input.chatModels) {
    if (seen.has(model.model_id)) continue
    seen.add(model.model_id)
    options.push({ value: model.model_id, label: modelOptionLabel(model) })
  }

  if (options.length === 0) {
    return { visible: false, options: [], emptyHint: CHAT_MODEL_EMPTY_HINT }
  }
  if (options.length === 1) {
    return { visible: false, options: [], emptyHint: '' }
  }
  return { visible: true, options, emptyHint: '' }
}
```

`EmbedChat.vue`：

1) `fetchModels` 改用聊天作用域接口，并把结果同时留存为 `chatScopedModels`：

```ts
const chatScopedModels = ref<AIModel[]>([]);
const fetchModels = async () => {
  try {
    const res = await modelApi.listAvailableForChat();
    if (res.data) {
      chatScopedModels.value = res.data.filter((m) => m.is_active);
      availableModels.value = chatScopedModels.value.filter(
        (m) => m.type === "llm" || m.type === "multimodal"
      );
    }
  } catch (e) {
    console.error("Failed to fetch models", e);
  }
};
```

2) 用纯函数产出输入框实际候选与可见性（替换 `manualModelSwitchAllowed` 的消费点）：

```ts
const chatModelSwitch = computed(() =>
  resolveChatModelSwitch({
    versionAllowsSwitch: manualModelSwitchAllowed.value,
    chatModels: availableModels.value,
    agentDefaultModel: currentAgentDefaultModel.value, // 选定智能体的已发布版本编排模型
  })
);
```

3) 越权提示：请求失败且状态码为 403 时，除既有错误提示外清掉本机 `config.overrideModel`（回落到智能体默认模型）：

```ts
if (isAxiosError(error) && error.response?.status === 403) {
  config.overrideModel = '';
  localStorage.removeItem('yovole_override_model');
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest -q tests/frontend/test_chat_model_whitelist_behavior.py`
Expected: PASS（6 项）

前端契约与类型：
Run: `.venv/bin/python -m pytest --confcutdir=tests/frontend -q tests/frontend`
Run: `cd frontend && node --max-old-space-size=6144 ./node_modules/vue-tsc/bin/vue-tsc.js --noEmit -p tsconfig.app.json`
Expected: 前端测试全绿；类型错误与基线一致（零新增）。

- [ ] **Step 5: 交付（由用户提交）**

```bash
# 由用户执行
git add frontend/src/utils/modelSelect.ts frontend/src/views/EmbedChat.vue \
        tests/frontend/test_chat_model_whitelist_behavior.py
git commit -m "feat(chat): 输入框候选并入智能体默认模型，越权时清理本机覆盖"
```

---

## Task 6: CHECKLIST 与整体回归

**Files:**
- Modify: `tests/CHECKLIST.md`

- [ ] **Step 1: 登记 CHECKLIST**

在表格末尾追加一行（6 列），写明：用户反馈原话（「有没有必要给用户指定白名单模型…不影响智能体默认配置的模型」「输入框这边需要保留智能体默认配置了的模型，默认模型 + 白名单列表」）、spec 与 plan 路径、改动文件、语义要点（空 = 不限制 / 并集 / 管理员直通 / 默认模型豁免 / 零迁移 / 缓存键 v3→v4）、验证结果、日期 `2026-10-13`。

- [ ] **Step 2: 全量回归**

Run: `.venv/bin/python -m pytest --confcutdir=tests/frontend -q tests/frontend`
Expected: 全绿（1750 + 新增）

Run: `.venv/bin/python -m pytest -q tests/services tests/api`
Expected: 仅剩改动前已存在的失败（若有，需与基线对比确认非本次引入）

Run: `cd frontend && node --max-old-space-size=6144 ./node_modules/vue-tsc/bin/vue-tsc.js --noEmit -p tsconfig.app.json`
Expected: 零新增类型错误

- [ ] **Step 3: 汇报并交付（由用户提交）**

```bash
# 由用户执行
git add tests/CHECKLIST.md
git commit -m "docs(checklist): 登记聊天模型白名单交付"
```

提醒用户：本次**无数据库迁移**，无需执行任何 SQL；重启与验收由用户在控制台执行 `./dev.sh`。

---

## Task 7: 权限弹窗「可用模型」页支持搜索（用户追加需求）

### Step 1（RED）：先写行为测试
新建 `tests/frontend/test_permission_model_filter_behavior.py`，用既有 node transpile harness 跑
`frontend/src/utils/modelSelect.ts` 的 `groupPermissionModels`，覆盖 10 个用例（selected/others 分组）：
空查询原序返回全部 / 按展示名命中 / 按 model_id 命中 / 大小写与首尾空格 / 无匹配返回空 /
已勾选但不匹配者置顶保留 / 已勾选且匹配者不重复 / 多个已选项保持原顺序 / 不改动入参 / `null` 输入。

同一提交里在 `tests/frontend/test_chat_model_whitelist_contract.py` 追加两条契约：
- `test_permission_model_page_supports_search`：`Roles.vue` / `Users.vue` 都出现
  `groupPermissionModels`、`modelSearchQuery`、`shouldShowModelSearch`、`搜索模型`、`已选 `、`其余 `；
- `test_chat_rejection_copy_is_wired_on_both_sides`：后端 detail 含「该模型不在你的可用范围内」
  且前端 403 判定用 `errorMessage.includes("可用范围")`——防止以后改文案导致前端清覆盖逻辑静默失效。

跑测试确认 RED（函数不存在 / 组件未接线）。

### Step 2（GREEN）：纯函数 + 组件接线
1. `frontend/src/utils/modelSelect.ts` 追加 `PermissionModelLike` 与 `groupPermissionModels`（实现见 spec §4.7.1）。
2. `Roles.vue` / `Users.vue`：
   - 引入 `groupPermissionModels` / `shouldShowModelSearch`，新增 `modelSearchQuery`；
   - `currentResources` 的 `models` 分支把 `[...selected, ...others]` 拍平（下游 `selectableResources` / `isAllSelected` / `toggleSelectAll` / 计数自动跟随，行为不变），渲染层另读 `modelResourceGroups` 插入「已选 N 个 / 其余 M 个」两段标题；
   - 搜索框仅在 `activeResTab === 'models'` 且 `shouldShowModelSearch(availableModels.length)` 时显示，
     放在说明文案与列表滚动容器之间，样式参照 `ChatInput.vue` 的模型搜索框；
   - 切换 Tab 时清空搜索词；空态文案区分「（没有匹配的模型）」。

### Step 3：验证
```bash
.venv/bin/python -m pytest -q tests/frontend/test_permission_model_filter_behavior.py \
  tests/frontend/test_chat_model_whitelist_contract.py
.venv/bin/python -m pytest --confcutdir=tests/frontend -q tests/frontend
cd frontend && node --max-old-space-size=6144 ./node_modules/vue-tsc/bin/vue-tsc.js --noEmit -p tsconfig.app.json
```
预期：前两条全绿；`vue-tsc` 错误数不超过基线 `/tmp/vuetsc-before.log`。

## 执行后修正（与计划的偏差，均已落地并验证）

计划是动手前写的，执行中按实际反馈修正了三处，记录在此以免后来者照旧文本理解代码：

1. **守卫函数的位置**：`_enforce_chat_model_whitelist` 必须定义在 `@router.post("/completions", …)` **装饰器之前**。
   第一次插在装饰器与 `async def create_chat_completion` 之间，FastAPI 把守卫当成了路由处理函数，启动即报
   `Invalid args for response field! … AsyncSession is a valid Pydantic field type`。
2. **候选不再并入智能体默认模型**（推翻 Task 5 的「并集」设计）：下拉的第一项本来就是 `ChatInput` 固有的
   「使用默认模型」（= 不下发覆盖、跟随智能体/平台默认），再单列一个「xxx · 智能体默认」候选项是重复的——
   两者点下去效果完全一样。最终实现改为**候选只来自白名单**（`resolveChatModelSwitch({versionAllowsSwitch, chatModels})`），
   阈值统一为「候选 ≥1 即显示」（下拉里「使用默认模型」+ 至少一个模型 = 至少两项可选），
   并删除 `agentDefaultModel` / `hasAgent` 两个入参与 `isAgentDefault` 标记。
3. **后端 `published_model_name` 已完整回退**（推翻 Task 3 的附加字段部分）：它唯一的用途是给第 2 点里那个候选项提供
   模型名，第 2 点落地后失去使用者，于是 `attach_published_model_switch_flags()` 恢复两列查询、`AIAgentResponse`
   删除该字段、相关 3 条测试移除。**端点校验豁免仍保留**：`published_agent_model_name()` 单查方法继续被
   `_enforce_chat_model_whitelist` 使用（防御「显式下发 = 智能体默认模型」被误拒）。

另外 Task 7（权限弹窗「可用模型」页的搜索与分组）是执行期间用户追加的需求，已按 spec §4.7.1 落地；其中第 4 点「已选置顶」在用户反馈「已选择了的模型被淹没了」后升级为**默认视图就分「已选 / 其余」两段**，纯函数也随之由 `filterPermissionModels`（拍平数组）改为 `groupPermissionModels`（返回 `{selected, others}`）。

## 自审

**1. Spec 覆盖检查**

| Spec 章节 | 对应任务 |
| --- | --- |
| §4.1 数据模型（零迁移） | Task 1（复用现表，无迁移） |
| §4.2 语义规则（空=不限制 / 并集 / 管理员直通 / 只约束显式覆盖 / 默认模型豁免） | Task 1（判据函数 + 纯函数）、Task 3（豁免） |
| §4.3 后端改动清单 | Task 1–3 |
| §4.4 `scope=chat` 过滤 | Task 2 |
| §4.5 端点层校验 | Task 3 |
| §4.6 缓存与生效时机（v3→v4） | Task 1 Step 3 |
| §4.7 权限弹窗资源页 | Task 4 |
| §4.8 组合语义与残留覆盖清理、并集为空提示 | Task 5 |
| §5 兼容性（管理端全量、旧前端不误删） | Task 1（`model_fields_set`）、Task 2（不带 scope 不过滤） |
| §7 测试计划 | 各任务 Step 1/4 |
| §8 验收标准 | Task 6 + 各任务测试 |

**2. 占位符扫描**：无 TBD / "实现时决定"；两处"以既有写法为准"（`AIAgentVersion` 的发布状态枚举、`_fetch_permission_details` 的循环结构）都给出了确定的锚点与回退规则，不是待定项。

**3. 类型一致性**：`get_chat_allowed_model_ids`（返回 `Optional[set[str]]`）在 Task 1 定义、Task 2/3 消费；`_resolve_allowed_model_ids(user_role, model_ids)` 命名一致；`published_agent_model_name(session, agent_id, version_id)` 在 Task 3 定义并只在该任务消费；`resolveChatModelSwitch(input)` 的字段名 `versionAllowsSwitch` / `chatModels` / `agentDefaultModel` 在 Task 5 的测试、实现、接线中一致；前端提交字段 `models` 与后端 `PermissionUpdate.models` 同名。

---

## 执行方式

计划已保存。建议**逐任务执行**（Task 1 → 6），每个任务跑完其测试后再进入下一个；Task 4/5 之前先确认 `vue-tsc` 基线（`/tmp/vuetsc-before.log`）仍可比对。
