"""契约：用例结束后，用例期间新增的智能体/用户必须被自动清理。

背景：`tests/api/portal/` 下的接口测试直连开发库，并通过真实 API 造数据
（`AuthService.generate_api_key("dup_admin_xxx")` + `POST /api/portal/agents/`），
历史上累积出 2416 个测试智能体与 6884 个测试账号，把智能体中心拖到 2422 条。

本契约锁定「每个用例自清理」的安全边界：
- 用例期间**新增**的智能体/用户，用例结束后必须消失；
- 快照之前就存在的行（真实业务智能体、既有账号）**一律不动**——这是防误删的关键。
"""

import importlib.util
import uuid
from pathlib import Path

from sqlalchemy import delete, select

ROOT = Path(__file__).resolve().parents[1]
CONFTEST = ROOT / "tests" / "conftest.py"


def _load_conftest_helpers():
    """加载 tests/conftest.py 的模块级辅助函数（与 redis flush 守卫的测试同一手法）。"""
    spec = importlib.util.spec_from_file_location("nanzi_test_conftest_teardown", CONFTEST)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


async def _insert_agent(session, name: str) -> str:
    from app.models.agent import AIAgent

    agent = AIAgent(
        id=str(uuid.uuid4()),
        name=name,
        display_name=name,
        agent_type="GENERAL",
        engine_type="LOCAL",
        is_system=False,
        is_enabled=True,
        created_by="teardown_guard_test",
    )
    session.add(agent)
    await session.commit()
    return agent.id


async def _insert_user(session, user_name: str) -> int:
    from app.models.user import User

    user = User(
        user_name=user_name,
        role="user",
        status=1,
        api_key_hash=f"teardown-guard-{uuid.uuid4().hex}",
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user.id


async def _agent_exists(agent_id: str) -> bool:
    from app.core.orm import AsyncSessionLocal
    from app.models.agent import AIAgent

    async with AsyncSessionLocal() as session:
        row = (
            await session.execute(select(AIAgent.id).where(AIAgent.id == agent_id))
        ).first()
        return row is not None


async def _user_exists(user_id: int) -> bool:
    from app.core.orm import AsyncSessionLocal
    from app.models.user import User

    async with AsyncSessionLocal() as session:
        row = (await session.execute(select(User.id).where(User.id == user_id))).first()
        return row is not None


async def test_purge_removes_agents_created_after_snapshot(db_session):
    """用例期间新建的智能体，清理后必须消失——否则测试数据继续无限累积。"""
    module = _load_conftest_helpers()
    snapshot = await module.take_test_data_snapshot()

    agent_id = await _insert_agent(db_session, _unique("teardown-probe"))
    assert await _agent_exists(agent_id) is True

    stats = await module.purge_test_data_since(snapshot)

    assert stats["agents"] >= 1, f"清理统计未包含新建智能体：{stats}"
    assert await _agent_exists(agent_id) is False, "新建的测试智能体没有被清理"


async def test_purge_keeps_agents_existing_before_snapshot(db_session):
    """快照之前就存在的智能体绝不能被删——真实业务智能体靠这条保护。"""
    module = _load_conftest_helpers()

    keeper_id = await _insert_agent(db_session, _unique("teardown-keeper"))
    try:
        snapshot = await module.take_test_data_snapshot()  # keeper 进入快照
        await module.purge_test_data_since(snapshot)
        assert await _agent_exists(keeper_id) is True, "快照内的既有智能体被误删了"
    finally:
        # 用 finally：断言失败时也要摘掉探针，否则会残留在开发库里
        from app.core.orm import AsyncSessionLocal
        from app.models.agent import AIAgent

        async with AsyncSessionLocal() as session:
            await session.execute(delete(AIAgent).where(AIAgent.id == keeper_id))
            await session.commit()


async def test_purge_removes_users_created_after_snapshot(db_session):
    """用例期间新建的账号（dup_admin_xxx 这类）必须被清理。"""
    module = _load_conftest_helpers()
    snapshot = await module.take_test_data_snapshot()

    user_id = await _insert_user(db_session, _unique("dup_admin"))
    assert await _user_exists(user_id) is True

    stats = await module.purge_test_data_since(snapshot)

    assert stats["users"] >= 1, f"清理统计未包含新建账号：{stats}"
    assert await _user_exists(user_id) is False, "新建的测试账号没有被清理"


async def test_purge_keeps_seed_accounts_created_after_snapshot(db_session):
    """seed 账号是测试基础设施（多个用例共用），即使晚于快照创建也要保留。"""
    module = _load_conftest_helpers()

    from app.core.orm import AsyncSessionLocal
    from app.models.user import User

    async with AsyncSessionLocal() as session:  # 先清掉，模拟"快照后才由 seed 创建"
        await session.execute(delete(User).where(User.user_name == "test_admin"))
        await session.commit()

    snapshot = await module.take_test_data_snapshot()
    seed_id = await _insert_user(db_session, "test_admin")

    await module.purge_test_data_since(snapshot)

    assert await _user_exists(seed_id) is True, "seed 账号被误删，会让依赖它的用例随机失败"


async def test_purge_clears_redis_session_index_for_removed_users(db_session):
    """删账号时必须摘掉 Redis 里的会话索引，否则缓存会继续指向已不存在的用户。

    真实事故：手工删掉旧 test_user（id=9）后 Redis 仍有它的认证缓存，重建后的
    test_user 换了新 id，于是 /auth/me 返回 9、写通知配置因外键失败报 500。
    """
    module = _load_conftest_helpers()
    snapshot = await module.take_test_data_snapshot()

    user_id = await _insert_user(db_session, _unique("dup_admin"))

    from app.core.redis import get_redis

    redis_client = await get_redis()
    index_key = f"auth:user_sessions:{user_id}"
    session_key = f"auth:api_key:{uuid.uuid4().hex}"
    await redis_client.sadd(index_key, session_key)

    await module.purge_test_data_since(snapshot)

    assert await redis_client.exists(index_key) == 0, "被删账号的会话索引键没有清理"
    assert await redis_client.exists(session_key) == 0, "索引里登记的会话键没有清理"


async def _insert_model(session, model_id: str) -> str:
    from app.models.ai_model import AIModel

    model = AIModel(
        id=str(uuid.uuid4()),
        name=model_id,
        model_id=model_id,
        provider="other",
        type="llm",
        is_active=True,
    )
    session.add(model)
    await session.commit()
    return model.id


async def _model_exists(pk: str) -> bool:
    from app.core.orm import AsyncSessionLocal
    from app.models.ai_model import AIModel

    async with AsyncSessionLocal() as session:
        row = (await session.execute(select(AIModel.id).where(AIModel.id == pk))).first()
        return row is not None


async def test_purge_removes_models_created_after_snapshot(db_session):
    """用例期间新建的模型必须被清理——否则模型管理页会像智能体中心一样被测试数据淹没。"""
    module = _load_conftest_helpers()
    snapshot = await module.take_test_data_snapshot()

    pk = await _insert_model(db_session, _unique("test-model"))
    assert await _model_exists(pk) is True

    stats = await module.purge_test_data_since(snapshot)

    assert stats["models"] >= 1, f"清理统计未包含新建模型：{stats}"
    assert await _model_exists(pk) is False, "新建的测试模型没有被清理"


async def test_purge_keeps_models_existing_before_snapshot(db_session):
    """快照之前就存在的模型绝不能被删——真实模型靠这条保护。"""
    module = _load_conftest_helpers()

    keeper = await _insert_model(db_session, _unique("keep-model"))
    try:
        snapshot = await module.take_test_data_snapshot()
        await module.purge_test_data_since(snapshot)
        assert await _model_exists(keeper) is True, "快照内的既有模型被误删了"
    finally:
        # 用 finally：断言失败时也要摘掉探针，否则会残留在开发库里
        from app.core.orm import AsyncSessionLocal
        from app.models.ai_model import AIModel

        async with AsyncSessionLocal() as session:
            await session.execute(delete(AIModel).where(AIModel.id == keeper))
            await session.commit()


async def test_purge_keeps_rows_created_outside_this_process(db_session):
    """只清本进程自己造的数据，别的测试进程建的行不能碰。

    开发中常有两个 pytest 进程共用一个开发库；若按「整表差集」清理，两边会互删
    对方刚建的行——实测表现为 POST 200 之后紧接着 PUT 404 /
    `StaleDataError: UPDATE ... 0 were matched`。这里用原生 SQL 插入模拟
    「另一个测试进程建的行」（绕过本进程的 ORM 追踪）。
    """
    module = _load_conftest_helpers()
    snapshot = await module.take_test_data_snapshot()

    from sqlalchemy import text
    from app.core.orm import AsyncSessionLocal

    foreign_pk = str(uuid.uuid4())
    async with AsyncSessionLocal() as session:
        await session.execute(
            text(
                "INSERT INTO ai_models (id, name, model_id, provider, type, is_active) "
                "VALUES (:id, 'foreign-probe', :mid, 'other', 'llm', 1)"
            ),
            {"id": foreign_pk, "mid": f"foreign-probe-{uuid.uuid4().hex}"},
        )
        await session.commit()

    try:
        await module.purge_test_data_since(snapshot)
        assert await _model_exists(foreign_pk) is True, (
            "清理越界：删掉了另一个测试进程创建的行，会造成对方的幽灵失败"
        )
    finally:
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("DELETE FROM ai_models WHERE id = :id"), {"id": foreign_pk}
            )
            await session.commit()


async def test_guard_defers_to_mocked_database_layer(monkeypatch):
    """纯单元测试会覆盖 init_infrastructure 并 patch 掉 AsyncSessionLocal。

    这类用例刻意不碰数据库，guard 必须让路：否则它会绕过被 mock 的连接池去用真实
    连接（conftest 顶层 `from app.core.orm import AsyncSessionLocal` 是绑定引用，
    patch 不到），撞上上一轮 event loop 残留的连接，抛
    `got Future attached to a different loop`——实测给
    tests/ai/test_chatbi_result_stack.py 制造了 9 个 error。
    """
    module = _load_conftest_helpers()

    from unittest.mock import MagicMock

    from app.core import orm

    monkeypatch.setattr(orm, "AsyncSessionLocal", MagicMock(name="mocked-sessionmaker"))
    assert module.infrastructure_is_real() is False


async def test_infrastructure_is_real_without_mocking():
    """正常（真连数据库）的用例里，guard 必须照常工作。"""
    module = _load_conftest_helpers()
    assert module.infrastructure_is_real() is True



async def test_guard_fixture_is_registered_as_autouse(request):
    """清理必须挂在 autouse fixture 上，否则没人记得调用它。"""
    assert "purge_test_data" in request.fixturenames
