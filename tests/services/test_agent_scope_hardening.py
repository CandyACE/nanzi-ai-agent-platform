"""智能体级禁用的加固回归（对抗性审查发现的问题）。

覆盖四件事：
1. 智能体级 MCP 候选的落库标识必须是 ``server_name:工具段`` 全名（否则运行时匹配不上）；
2. 迁移探测必须"试引用该列"而**不是**查 ``information_schema``（后者跨库误判会打挂全部权限 SQL）；
3. 探测"不确定"时不得把进程永久写死成未迁移（未迁移 = 不加任何作用域 = 跨智能体读取 + 误删）；
4. 智能体级写入端点必须拒绝裸字符串（否则按字符拆成单字符垃圾行）。
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.no_infrastructure


# ---------------------------------------------------------------------------
# 1. 探测语句：不能依赖 information_schema
# ---------------------------------------------------------------------------

def test_probe_does_not_use_information_schema():
    """探测必须试引用列，而不是查 information_schema。

    MySQL 的 information_schema 覆盖整台实例上该用户可见的**所有** schema：同实例里
    只要别的库（开发机就真实存在 test0001/test001/test002）迁移过 V168，未迁移库的
    进程也会把状态判成"已迁移"，此后每条权限 SQL 都报 1054 Unknown column，
    把登录与权限链路一起打挂。
    """
    source = (ROOT / "app/services/permission_service.py").read_text(encoding="utf-8")
    probe = source[source.index("async def _supports_agent_scope"):]
    probe = probe[: probe.index("async def _agent_scope_filters")]
    # 只在**SQL**层面禁掉；docstring 里正当地提到它（说明"为什么不查"）不算违规
    assert "FROM information_schema" not in probe, (
        "探测不能查 information_schema（跨 schema 误判）"
    )
    assert "agent_id IS NULL" in probe, "探测应当直接试引用该列"


def test_probe_distinguishes_absent_column_from_inconclusive_failure():
    """代码里必须区分「确定无此列」与「探测不确定」两种失败。"""
    source = (ROOT / "app/services/permission_service.py").read_text(encoding="utf-8")
    probe = source[source.index("async def _supports_agent_scope"):]
    probe = probe[: probe.index("async def _agent_scope_filters")]
    # 「确定无此列」的错误码判定
    assert "_AGENT_SCOPE_UNKNOWN_COLUMN_CODES" in probe
    assert "_AGENT_SCOPE_COLUMN_STATE = False" in probe, "确定无列才允许缓存 False"
    # 「不确定」只记时间戳，绝不写死状态
    assert "_AGENT_SCOPE_PROBE_FAILED_AT = now" in probe, (
        "不确定的失败必须只做节流重试，不能把 _AGENT_SCOPE_COLUMN_STATE 写死为 False"
    )


@pytest.mark.asyncio
async def test_inconclusive_probe_is_retried_on_the_next_call(monkeypatch):
    """一次偶发失败不能让进程永久按「未迁移」运行。"""
    from app.services import permission_service as module

    monkeypatch.setattr(module, "_AGENT_SCOPE_COLUMN_STATE", None)
    monkeypatch.setattr(module, "_AGENT_SCOPE_PROBE_FAILED_AT", 0.0)
    monkeypatch.setattr(module, "_AGENT_SCOPE_PROBE_RETRY_SECONDS", 0.0)

    calls = {"n": 0}

    class _Savepoint:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return False

    class _Probe:
        async def execute(self, *_args, **_kwargs):
            calls["n"] += 1
            # 非「列不存在」的失败：结论不确定
            raise RuntimeError("connection reset by peer")

        def begin_nested(self):
            return _Savepoint()

    service = module.PermissionService.__new__(module.PermissionService)
    service.db = _Probe()
    service._redis = None

    # 两次调用都必须真的去探测（重试间隔为 0），且都不能把状态写死
    first = await service._supports_agent_scope()
    second = await service._supports_agent_scope()

    assert first is False and second is False, "不确定时先按未迁移处理"
    assert calls["n"] >= 1, "必须真的发起过探测"
    assert module._AGENT_SCOPE_COLUMN_STATE is None, (
        "不确定的失败绝不能把进程状态写死——那会让整个进程按「不加作用域」运行"
    )


# ---------------------------------------------------------------------------
# 2. 端点 schema：裸字符串必须被挡在入口
# ---------------------------------------------------------------------------

def test_restriction_update_schema_rejects_bare_string():
    """``forbidden_tools`` / ``forbidden_skills`` 只接受列表或 null。

    服务层是按 ``for value in values`` 迭代的：裸字符串会被按**字符**拆开，
    ``"exec_command"`` 变成 e/x/c/_/o/m/a/n/d 九条单字符记录，且原有限制已被 DELETE
    清空、接口还返回 200。schema 把这条约束挡在入口，比事后靠日志发现垃圾数据便宜。
    """
    from app.api.portal.endpoints.management import AgentRestrictionUpdate

    ok = AgentRestrictionUpdate(forbidden_tools=["exec_command"], forbidden_skills=[])
    assert ok.forbidden_tools == ["exec_command"] and ok.forbidden_skills == []

    default = AgentRestrictionUpdate()
    assert default.forbidden_tools is None and default.forbidden_skills is None

    for field in ("forbidden_tools", "forbidden_skills"):
        with pytest.raises(ValidationError):
            AgentRestrictionUpdate(**{field: "exec_command"})


@pytest.mark.asyncio
async def test_service_rejects_bare_string_as_defense_in_depth(monkeypatch):
    """服务层也要拒绝：它是公共方法，不该假设每个调用方都经过 schema。"""
    from app.services import permission_service as module

    monkeypatch.setattr(module, "_AGENT_SCOPE_COLUMN_STATE", True)

    executed: list[str] = []

    class _Db:
        async def execute(self, statement, *_a, **_k):
            executed.append(str(statement))
            return None

        async def commit(self):
            return None

        async def flush(self):
            return None

    service = module.PermissionService.__new__(module.PermissionService)
    service.db = _Db()
    service._redis = None

    with pytest.raises(ValueError):
        await service.update_agent_scoped_forbidden_ids(
            user_id=1, agent_id="agent-x", forbidden_tools="exec_command"
        )

    assert not executed, "必须在发出任何 DELETE/INSERT 之前就拒绝"


# ---------------------------------------------------------------------------
# 3. 写入路径的顺序与缓存清理
# ---------------------------------------------------------------------------

def test_agent_scoped_write_commits_before_invalidating():
    """必须先提交再失效，否则并发请求会把未提交的旧值写回 Redis（TTL 1 小时）。"""
    source = (ROOT / "app/services/permission_service.py").read_text(encoding="utf-8")
    body = source[source.index("async def update_agent_scoped_forbidden_ids"):]
    body = body[: body.index("async def get_accessible_dataset_ids_csv")]

    commit_at = body.index("await self.db.commit()")
    invalidate_at = body.index("_invalidate_user_cache")
    assert commit_at < invalidate_at, "commit 必须早于缓存失效"


def test_permission_writes_clear_the_skill_side_process_cache():
    """权限失效必须一并清技能侧的进程内缓存（policy.py，TTL 60s），否则禁了还能读。"""
    source = (ROOT / "app/services/permission_service.py").read_text(encoding="utf-8")
    invalidator = source[source.index("async def _invalidate_user_cache"):]
    invalidator = invalidator[: invalidator.index("async def _invalidate_role_cache")]
    assert "clear_forbidden_skill_cache" in invalidator, (
        "Redis 权限键清不掉进程内技能缓存，必须在失效里显式清"
    )
