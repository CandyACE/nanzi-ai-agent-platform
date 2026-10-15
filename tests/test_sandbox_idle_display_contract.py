"""契约：浮标上的「空闲 Xm 自动回收」必须来自 `sandbox_idle_time`，不得写死。

用户截图取证：管理台已把 `sandbox_idle_time` 改成 15 分钟，输入框浮标仍显示
"空闲 30m 自动回收"——原因是 `ChatInput.vue` 的 `sandboxReclaimHint` 把 30 分钟
硬编码在组件里，与回收器实际使用的阈值没有任何关系。

这里钉住三件事：
    * 前端只能通过 prop 读取分钟数，拿不到时只说「空闲超时」，不编造数字；
    * 后端上下文使用接口暴露 `sandbox_idle_minutes`，且与回收器**同源**（同一个解析函数）；
    * 解析函数本身按配置走、非法配置回退默认。

关于函数名：解析函数曾名 `_effective_sandbox_idle_seconds`，后提升为公共名
`resolve_effective_sandbox_idle_seconds`（保留旧名别名）。本契约只要求「取到的是回收器
用的那一个函数」，不绑定具体名字——重命名与接口改动可能分离落地，契约不应因此变红。
"""
from pathlib import Path

import pytest

pytestmark = pytest.mark.no_infrastructure

ROOT = Path(__file__).resolve().parents[1]

RESOLVER_NAMES = ("resolve_effective_sandbox_idle_seconds", "_effective_sandbox_idle_seconds")


def _resolver(workspace_module):
    """按「优先公共名、回退旧名」取解析函数（与 chat.py 的取用口径一致）。"""
    for name in RESOLVER_NAMES:
        func = getattr(workspace_module, name, None)
        if func is not None:
            return func
    raise AssertionError("沙箱模块没有暴露空闲时长解析函数")


def test_chat_input_reclaim_hint_reads_prop_instead_of_hardcoding():
    source = (ROOT / "frontend/src/components/embed/ChatInput.vue").read_text(
        encoding="utf-8"
    )

    assert "sandboxIdleMinutes?: number | null" in source
    assert "props.sandboxIdleMinutes" in source

    # 旧的写死文案不得回归（注释里提到历史文案不算，因此先剔除注释行）
    code_lines = [
        line for line in source.split("\n") if not line.strip().startswith(("//", "*"))
    ]
    assert not any("空闲 30m" in line for line in code_lines), (
        "浮标回收时长又被写死了：必须来自后端 sandbox_idle_minutes"
    )
    # 拿不到配置时的兜底不编造具体分钟数
    assert "空闲超时自动回收" in source


def test_chat_pages_pass_idle_minutes_from_context_usage():
    for rel in (
        "frontend/src/views/EmbedChat.vue",
        "frontend/src/views/AgentDebug.vue",
    ):
        source = (ROOT / rel).read_text(encoding="utf-8")
        assert (
            ':sandbox-idle-minutes="contextUsage?.sandbox_idle_minutes ?? null"' in source
        ), f"{rel} 没有把 sandbox_idle_minutes 透传给 ChatInput"

    usage = (ROOT / "frontend/src/composables/useContextUsage.ts").read_text(
        encoding="utf-8"
    )
    assert "sandbox_idle_minutes?: number | null" in usage


def test_backend_context_usage_exposes_idle_minutes_from_single_source():
    chat = (ROOT / "app/api/v1/endpoints/chat.py").read_text(encoding="utf-8")
    assert '"sandbox_idle_minutes": sandbox_idle_minutes' in chat
    # 必须复用回收器的解析函数，而不是自己再解析一遍配置（否则两处口径会漂移）；
    # 两个名字都要能被取到，重命名未同步时不能降级成"浮标没有数字"。
    assert "resolve_effective_sandbox_idle_seconds" in chat
    assert "_effective_sandbox_idle_seconds" in chat

    workspace = (
        ROOT / "app/services/ai/runtime/agentscope/workspace.py"
    ).read_text(encoding="utf-8")
    assert any(name in workspace for name in RESOLVER_NAMES)
    # 创建期、回收期都必须走这一个解析函数
    assert "_effective_sandbox_idle_seconds(" in workspace


@pytest.mark.asyncio
async def test_resolve_effective_idle_seconds_follows_config(monkeypatch):
    from app.services.ai.runtime.agentscope import workspace as ws

    resolve = _resolver(ws)

    async def _configured(key, default=None):
        assert key == ws.SANDBOX_IDLE_TIME_KEY
        return "15"

    monkeypatch.setattr("app.services.config_service.ConfigService.get", _configured)
    assert (
        await resolve(default_seconds=1800.0) == 900.0
    ), "配了 15 分钟就必须按 15 分钟走（回收器与浮标同源）"

    async def _illegal(key, default=None):
        return "not-a-number"

    monkeypatch.setattr("app.services.config_service.ConfigService.get", _illegal)
    assert (
        await resolve(default_seconds=1800.0) == 1800.0
    ), "非法配置必须回退到调用方默认值"

    # 若重命名已落地，旧名必须是同一个函数（历史调用点不受影响）
    public = getattr(ws, "resolve_effective_sandbox_idle_seconds", None)
    if public is not None:
        assert ws._effective_sandbox_idle_seconds is public
