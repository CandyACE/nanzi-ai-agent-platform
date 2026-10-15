"""契约：沙箱「刷新」按钮必须有"刷新中"反馈（转圈 + 禁用），防重入也不能静默。

用户截图取证：点「刷新」没有任何动画。根因不是"沙箱没启动"，而是两件事：
    * 刷新按钮的转圈条件只绑定容器启停状态（`starting` / `stopping`），那是"容器在启停"
      的指示，与"正在刷新"无关——沙箱 running 时点刷新同样不转；
    * 刷新请求的"在飞行中"只是一个**普通变量** `sandboxStatusRefreshInFlight`，既不是
      响应式也没暴露给组件，所以 UI 无从知道；且请求未回来时再点会被静默 `return`，
      连 toast 都没有，表现为"点了完全没反应"。

这里钉住：刷新状态是响应式的、暴露给组件、驱动转圈与禁用，且最短可见时长保证"点到了"
这件事看得出来。
"""
from pathlib import Path

import pytest

pytestmark = pytest.mark.no_infrastructure

ROOT = Path(__file__).resolve().parents[2]
COMPOSABLE = "frontend/src/composables/chat/useSandboxWorkspace.ts"
CHAT_INPUT = "frontend/src/components/embed/ChatInput.vue"
PAGES = ("frontend/src/views/EmbedChat.vue", "frontend/src/views/AgentDebug.vue")


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_composable_exposes_reactive_refreshing_state():
    source = _read(COMPOSABLE)

    assert "const sandboxWorkspaceRefreshing = ref(false);" in source, (
        "刷新中状态必须是响应式 ref（此前只有普通变量，UI 看不到）"
    )
    # 进入刷新时置位、结束时复位
    assert "sandboxWorkspaceRefreshing.value = true;" in source
    assert "sandboxWorkspaceRefreshing.value = false;" in source
    # 必须暴露给页面
    assert "sandboxWorkspaceRefreshing," in source


def test_composable_keeps_spinner_visible_and_reentry_not_silent():
    source = _read(COMPOSABLE)

    # 最短可见时长：接口几十毫秒返回时，否则动画一闪而过等于没有
    assert "SANDBOX_REFRESH_MIN_SPIN_MS" in source
    assert "elapsed < SANDBOX_REFRESH_MIN_SPIN_MS" in source
    # 但只对手动刷新生效：watch(immediate)/polling 触发的内部刷新后面紧跟自动预热，
    # 不该为了动画被拖慢
    finally_block = source.split("} finally {", 1)[1]
    assert "if (showFeedback)" in finally_block.split("sandboxWorkspaceRefreshing.value = false")[0]

    # 防重入保留，但要有反馈（否则用户以为按钮坏了）
    assert "正在刷新沙箱状态，请稍候…" in source


def test_chat_input_spins_and_disables_while_refreshing():
    source = _read(CHAT_INPUT)

    assert "sandboxRefreshing?: boolean" in source
    # 转圈条件必须包含刷新中状态，且不能只依赖容器启停状态
    spin_line = next(
        (line for line in source.split("\n") if "animate-spin" in line and "ArrowPathIcon" in line),
        "",
    )
    assert "sandboxRefreshing ||" in spin_line, (
        "刷新按钮的转圈必须由 sandboxRefreshing 驱动，而不是只跟随容器启停状态"
    )
    assert ':disabled="sandboxRefreshing"' in source


def test_pages_pass_refreshing_flag_to_chat_input():
    for rel in PAGES:
        source = _read(rel)
        assert ':sandbox-refreshing="sandboxWorkspaceRefreshing"' in source, (
            f"{rel} 没有把刷新中状态透传给 ChatInput"
        )
        assert "sandboxWorkspaceRefreshing," in source, (
            f"{rel} 没有从 composable 解构出 sandboxWorkspaceRefreshing"
        )
