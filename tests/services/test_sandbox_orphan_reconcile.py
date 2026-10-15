"""沙箱销毁机制的两条补强：执行期心跳 + 孤儿容器/Pod 对账。

背景（本次审计发现）：
1. 空闲回收只看 ``last_used``，而它此前只在「拉起沙箱/缓存命中/Bash 调用开始前」
   刷新：一条执行超过 ``sandbox_idle_time`` 的命令会被 reaper 关掉正在用的沙箱。
2. 回收只遍历进程内字典，进程重启或技能集合令牌变化后留下的容器/Pod 再也无人认领
   （``as_ws_<user>`` 这类历史命名连同名替换都蹭不到），会永久驻留。
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.services.ai.runtime.agentscope import workspace as ws

pytestmark = pytest.mark.no_infrastructure


def _container(*, workspace_id: str, created: float, name: str) -> SimpleNamespace:
    item = SimpleNamespace(
        _container={
            "Labels": {
                "agentscope.workspace": "true",
                "agentscope.workspace.id": workspace_id,
            },
            "Created": created,
            "Names": [f"/{name}"],
        },
        id=name,
        deleted=False,
    )

    async def _delete(force: bool = False) -> None:
        item.deleted = True

    item.delete = _delete
    return item


class _FakeDocker:
    def __init__(self, items: list[SimpleNamespace]) -> None:
        self.closed = False

        async def _close() -> None:
            self.closed = True

        self.containers = SimpleNamespace(
            list=self._list, close=_close
        )
        self._items = items

    async def _list(self, all: bool = True, filters: dict | None = None):
        return list(self._items)

    async def close(self) -> None:
        self.closed = True


@pytest.fixture(autouse=True)
def _clean_caches():
    ws.clear_workspace_cache()
    yield
    ws.clear_workspace_cache()


@pytest.mark.asyncio
async def test_reconcile_reclaims_only_untracked_and_old_containers(monkeypatch):
    """活跃条目对应的容器不删；不在注册表里且创建够久的容器删掉。"""
    now = time.time()
    live_id = "user__1-aaaaaaaaaaaa"
    live = _container(workspace_id=live_id, created=now - 7200, name=f"as_ws_{live_id}")
    legacy_orphan = _container(
        workspace_id="user__1", created=now - 7200, name="as_ws_user__1"
    )
    fresh_orphan = _container(
        workspace_id="user__2-bbbbbbbbbbbb", created=now - 30, name="as_ws_user__2-bbbbbbbbbbbb"
    )

    ws._docker_workspace_cache[f"root::{live_id}::aaaaaaaaaaaa::docker"] = SimpleNamespace(
        _platform_workspace_id=live_id
    )

    import aiodocker

    fake = _FakeDocker([live, legacy_orphan, fresh_orphan])
    monkeypatch.setattr(aiodocker, "Docker", lambda *a, **k: fake)

    removed = await ws.reconcile_orphan_docker_workspaces(now=now)

    assert removed == 1
    assert live.deleted is False, "注册表内的活跃沙箱不能被对账回收"
    assert legacy_orphan.deleted is True, "脱离注册表的历史命名容器必须被回收"
    assert fresh_orphan.deleted is False, "刚创建的沙箱必须留出宽限，不能被误删"
    assert fake.closed is True


@pytest.mark.asyncio
async def test_reconcile_skips_when_creation_time_is_unknown(monkeypatch):
    """拿不到创建时间时保守跳过：宁可留一台孤儿也不误删刚拉起的沙箱。"""
    orphan = _container(workspace_id="user__9", created=0.0, name="as_ws_user__9")

    import aiodocker

    monkeypatch.setattr(aiodocker, "Docker", lambda *a, **k: _FakeDocker([orphan]))

    assert await ws.reconcile_orphan_docker_workspaces(now=time.time()) == 0
    assert orphan.deleted is False


@pytest.mark.asyncio
async def test_orphan_reconcile_flag_reads_config(monkeypatch):
    async def _fake_get(key, default=None):
        assert key == ws.SANDBOX_ORPHAN_RECONCILE_KEY
        return "false"

    monkeypatch.setattr("app.services.config_service.ConfigService.get", _fake_get)
    assert await ws._orphan_reconcile_enabled() is False

    async def _dummy_get(key, default=None):
        raise RuntimeError("config unavailable")

    monkeypatch.setattr("app.services.config_service.ConfigService.get", _dummy_get)
    assert await ws._orphan_reconcile_enabled() is True, "读不到配置时按开启处理"


@pytest.mark.asyncio
async def test_sandbox_activity_heartbeat_refreshes_last_used(monkeypatch):
    """心跳必须在命令执行期间持续刷新活跃时间（否则长命令会被 reaper 关掉）。"""
    cache_key = "root::u1::aaaaaaaaaaaa::docker"
    ws._docker_workspace_cache[cache_key] = SimpleNamespace(
        _platform_workspace_id="u1-aaaaaaaaaaaa"
    )
    ws._docker_workspace_last_used[cache_key] = 0.0

    async def _fake_idle(*, default_seconds: float) -> float:
        return 0.02

    monkeypatch.setattr(ws, "_effective_sandbox_idle_seconds", _fake_idle)
    monkeypatch.setattr(ws, "SANDBOX_ACTIVITY_HEARTBEAT_MIN_SECONDS", 0.01)

    async with ws._sandbox_activity_heartbeat(cache_key=cache_key):
        # 人为清零：进入上下文时的那一次 touch 不算，只有心跳能把它刷新回来
        ws._docker_workspace_last_used[cache_key] = 0.0
        await asyncio.sleep(0.06)

    assert ws._docker_workspace_last_used[cache_key] > 0.0


@pytest.mark.asyncio
async def test_sandbox_activity_heartbeat_is_noop_without_key():
    """没有沙箱键（纯宿主策略）时上下文必须安全直通。"""
    async with ws._sandbox_activity_heartbeat():
        await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_lazy_bash_tool_heartbeats_during_long_command(monkeypatch):
    """真实 Bash 入口：命令执行期间必须持续刷新活跃时间。"""
    cache_key = "root::u1::aaaaaaaaaaaa::docker"
    ws._docker_workspace_cache[cache_key] = SimpleNamespace(
        _platform_workspace_id="u1-aaaaaaaaaaaa"
    )

    class _FakeRealTool:
        async def __call__(self, **kwargs):
            # 模拟一条长命令：执行期间没有任何显式 touch
            ws._docker_workspace_last_used[cache_key] = 0.0
            await asyncio.sleep(0.06)
            return "ok"

    async def _fake_idle(*, default_seconds: float) -> float:
        return 0.02

    monkeypatch.setattr(ws, "_effective_sandbox_idle_seconds", _fake_idle)
    monkeypatch.setattr(ws, "SANDBOX_ACTIVITY_HEARTBEAT_MIN_SECONDS", 0.01)

    proxy = ws.LazySandboxWorkspaceProxy(
        policy="docker", root="root", user_key="u1", skill_paths=None
    )
    proxy._sandbox_cache_key = cache_key
    tool = ws.LazySandboxBashNativeTool(proxy)

    async def _resolve() -> object:
        return _FakeRealTool()

    monkeypatch.setattr(tool, "_resolve_real_tool", _resolve)

    assert await tool(command="sleep 3600") == "ok"
    assert ws._docker_workspace_last_used[cache_key] > 0.0


@pytest.mark.asyncio
async def test_reconcile_k8s_reclaims_untracked_pod(monkeypatch):
    """K8s 侧同构：不在注册表里且创建够久的 Pod 被删除。"""
    k8s_client = pytest.importorskip("kubernetes_asyncio.client")
    k8s_config = pytest.importorskip("kubernetes_asyncio.config")
    from app.services.ai.runtime.agentscope import k8s_workspace as kws

    old = datetime.now(timezone.utc) - timedelta(hours=3)
    orphan_pod = SimpleNamespace(
        metadata=SimpleNamespace(
            name="as-ws-user--1",
            labels={"agentscope.workspace.id": "user__1"},
            creation_timestamp=old,
        )
    )
    live_pod = SimpleNamespace(
        metadata=SimpleNamespace(
            name="as-ws-user--1-aaaaaaaaaaaa",
            labels={"agentscope.workspace.id": "user__1-aaaaaaaaaaaa"},
            creation_timestamp=old,
        )
    )

    deleted: list[str] = []

    class _FakeCoreV1:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def list_namespaced_pod(self, namespace=None, label_selector=None):
            return SimpleNamespace(items=[orphan_pod, live_pod])

        async def delete_namespaced_pod(self, name=None, namespace=None):
            deleted.append(name)

    class _FakeApiClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(k8s_client, "ApiClient", _FakeApiClient)
    monkeypatch.setattr(k8s_client, "CoreV1Api", _FakeCoreV1)
    monkeypatch.setattr(k8s_config, "load_incluster_config", lambda: None)
    monkeypatch.setattr(kws, "resolve_sandbox_namespace", lambda configured: "agent-sandboxes")

    async def _fake_get(key, default=None):
        return default

    monkeypatch.setattr("app.services.config_service.ConfigService.get", _fake_get)

    ws._k8s_workspace_cache["root::user__1::aaaaaaaaaaaa::k8s"] = SimpleNamespace(
        _platform_workspace_id="user__1-aaaaaaaaaaaa"
    )

    assert await ws.reconcile_orphan_k8s_workspaces() == 1
    assert deleted == ["as-ws-user--1"]
