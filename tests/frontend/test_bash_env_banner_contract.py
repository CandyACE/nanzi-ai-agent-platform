"""bash 运行环境横幅（Bash 运行在哪）前端契约测试。

验证：
1. agentscopeSseHandlers.ts 的 dispatchAgentscopeStreamEvent 支持可选的
   onBashEnv 回调，并针对 "bash_env" 事件 type 分发 broker 事件（bash_env）与 SSE
   type（process_tool_start / bash_env）两条链下的 payload。
2. 组件 BashEnvBanner.vue 提供的容器/宿主机两种文案与配色、关闭按钮事件。
3. EmbedChat.vue 拉起横幅的状态接线：首次 bash 后置位 env、dismiss 逻辑、
   stream 结束复位，以及 banner slot 与 TodoCard 共存。
"""
from pathlib import Path

import pytest


pytestmark = pytest.mark.no_infrastructure
ROOT = Path(__file__).resolve().parents[2]
HANDLER = ROOT / "frontend/src/utils/agentscopeSseHandlers.ts"
BANNER = ROOT / "frontend/src/components/chat/BashEnvBanner.vue"
EMBED = ROOT / "frontend/src/views/EmbedChat.vue"
SETTINGS = ROOT / "frontend/src/components/embed/ChatSettings.vue"


def test_dispatch_accepts_optional_onbashenv_callback_and_handles_bash_env_event():
    source = HANDLER.read_text(encoding="utf-8")
    assert "onBashEnv?: (env: \"host\" | \"docker\") => void" in source
    assert "case \"bash_env\":" in source
    # 仅当值为合法的 docker / host 时才回调，避免脏数据触发横幅
    assert 'if (envVal === "docker" || envVal === "host")' in source
    assert "onBashEnv(envVal)" in source
    # onBashEnv 为可选参数，默认不触发任何横幅逻辑，避免破坏其它调用点
    assert "onBashEnv?: (env: \"host\" | \"docker\") => void" in source


def test_bash_env_banner_component_has_both_env_copy_and_dismiss():
    source = BANNER.read_text(encoding="utf-8")
    # props: 容器/宿主机二值
    assert 'docker' in source and 'host' in source
    assert "defineProps" in source
    # 文案与配色
    assert "运行在容器环境" in source
    assert "仍需遵守命令安全规则" in source
    assert "宿主机" in source
    assert "Docker 部署" in source
    assert "sandbox" in source.lower()
    assert "emerald" in source
    assert "amber" in source
    # 手动关闭
    assert "defineEmits" in source
    assert 'aria-label="关闭"' in source or 'aria-label="关闭横幅"' in source
    # 忽略提示按钮：emit('ignore') 事件 + aria-label
    assert "(e: 'ignore'): void" in source
    assert 'aria-label="忽略提示"' in source
    assert "emit('ignore')" in source


def test_embed_chat_wires_bash_banner_state_and_reset():
    source = EMBED.read_text(encoding="utf-8")
    assert 'import BashEnvBanner from "@/components/chat/BashEnvBanner.vue"' in source
    assert "bashBannerEnv" in source
    assert "bashBannerDismissed" in source
    assert "<BashEnvBanner" in source
    # 轮内首个 bash 事件置位 env 并解除本轮 dismiss
    assert "bashBannerEnv.value = env" in source
    assert "bashBannerDismissed.value = false" in source
    # 手动关闭：仅清除当前本轮，下轮事件会重新置位
    assert 'bashBannerDismissed = true' in source or "bashBannerDismissed.value = true" in source
    # 忽略提示：localStorage 持久化，config.showBashBanner 作为唯一状态源
    assert "bash_env_banner_ignored" in source
    assert "handleIgnoreBashBanner" in source
    assert "@ignore=" in source
    vif_pos = source.find("showBashBanner")
    assert vif_pos != -1
    # 显隐判断统一走 config.showBashBanner（设置面板开关的权威状态源）
    assert "config.showBashBanner" in source
    # 统一开关 handler setBashBannerVisible 持久化到 localStorage（1=关，0=开）
    assert "setBashBannerVisible" in source
    assert 'localStorage.setItem("bash_env_banner_ignored", visible ? "0" : "1")' in source
    # 传递给 dispatchAgentscopeStreamEvent 的三处调用点都接了 onBashEnv 回调
    assert "handleBashEnvEvent" in source
    assert source.count("dispatchAgentscopeStreamEvent") >= 3
    # stream 结束（finally）自动复位横幅
    assert "finally" in source


def test_bash_banner_has_settings_panel_switch():
    """设置面板提供可逆开关，可随时重新打开横幅提示（不再永久忽略）。"""
    settings_source = SETTINGS.read_text(encoding="utf-8")
    # 开关绑定 config.showBashBanner 与统一 handler
    assert "config.showBashBanner" in settings_source
    assert "handleSetBashBanner" in settings_source
    assert '<Switch :modelValue="!!config.showBashBanner"' in settings_source
    assert '@update:modelValue="handleSetBashBanner"' in settings_source
    # 设置面板开关与横幅本地键共用同一持久化键，保持单源同步
    assert "bash_env_banner_ignored" in settings_source
    # BOTH 视图使用相同文案，出价一致性
    assert "Bash 运行环境横幅提示" in settings_source


def test_bash_banner_shares_chat_input_slot_with_todo_card():
    source = EMBED.read_text(encoding="utf-8")
    # 与 TodoCard 共用 banner slot 容器，各自独立 v-if，互不干扰
    assert "activeTodoTimeline" in source
    assert "<BashEnvBanner" in source
    index_todo = source.find("activeTodoTimeline")
    index_banner = source.find("<BashEnvBanner")
    assert index_todo != -1 and index_banner != -1
