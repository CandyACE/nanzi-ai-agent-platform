"""EmbedChat 小程序宿主适配契约测试。

只做源码静态断言（沿用 tests/frontend 既有风格），不启动浏览器。
"""

from pathlib import Path

import pytest

pytestmark = pytest.mark.no_infrastructure

ROOT = Path(__file__).resolve().parents[2]
VIEW = ROOT / "frontend/src/views/EmbedChat.vue"


def test_view_exists():
    assert VIEW.exists(), f"缺少视图文件: {VIEW}"


def test_detects_miniprogram_host():
    view = VIEW.read_text(encoding="utf-8")

    # 微信 JSSDK 注入的环境标记；UA 作为兜底
    assert "__wxjs_environment" in view
    assert "miniProgram" in view
    assert "isMiniprogramHost" in view


def test_file_open_is_redirected_to_native_page():
    view = VIEW.read_text(encoding="utf-8")

    assert "/pages/file/file" in view
    assert "openFileInMiniapp" in view
    assert "navigateTo" in view


def test_credential_failure_can_relaunch_chat_page():
    """凭证失效时让小程序重新签票，而不是把用户留在白屏。"""
    view = VIEW.read_text(encoding="utf-8")

    assert "/pages/chat/chat" in view
    assert "relaunchMiniappChat" in view
    assert "reLaunch" in view


def test_has_no_agent_fallback_copy():
    """只断言字符串存在是「假通过」：必须确认常量真的被模板渲染。

    并且兜底文案要限定在「小程序宿主 + 列表为空」的分支内，
    否则会改变浏览器 / iframe 嵌入场景的既有行为。
    """
    view = VIEW.read_text(encoding="utf-8")

    assert "尚未开放智能体，请联系管理员" in view
    assert "{{ MINIPROGRAM_NO_AGENT_HINT }}" in view
    assert "isMiniprogramHost() && !isLoadingAgents && allowedAgents.length === 0" in view


def test_does_not_rely_on_postmessage_for_realtime_flow():
    """postMessage 只在后退/销毁/分享时批量触发，不能用于实时通知。"""
    view = VIEW.read_text(encoding="utf-8")

    assert "miniProgram.postMessage" not in view
