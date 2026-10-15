"""EmbedPersonal 返回对话入口契约测试。

背景：`/embed/personal` 是给第三方 iframe 嵌入的个人中心，刻意不带 Dashboard 导航
（设计注释写明「只出现个人中心本身」）。但对话页头部的「我的账号」会跳到它——
**小程序 web-view 里小程序的返回键是退出整个 web-view，而不是回退站内路由**，
没有返回入口用户就会卡在个人中心并丢掉对话上下文。

因此：从 `/embed/chat` 跳进来时必须出现「返回对话」；而第三方 iframe 直接打开本页时
不该凭空多出一个返回键。

浮标的五条约束（均为实测反馈后逐轮修正）：右下角（左上角会压住 tab 栏）、
`sm:hidden`（宽屏 Web 有完整导航可回退，浮标多余）、`min-h-11` 达到 44px 触控热区、
实底 + 可见边界（压在内容之上仍要读得清）。
其中「低调」只指**不用强调色**，不指降尺寸、也不指降对比度。

只做源码静态断言（沿用 tests/frontend 既有风格），不启动浏览器。
"""

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.no_infrastructure

ROOT = Path(__file__).resolve().parents[2]
VIEW = ROOT / "frontend/src/views/EmbedPersonal.vue"
CHAT = ROOT / "frontend/src/views/EmbedChat.vue"


def _view() -> str:
    return VIEW.read_text(encoding="utf-8")


def test_view_exists():
    assert VIEW.exists(), f"缺少视图文件: {VIEW}"


def test_chat_links_here_via_embed_route():
    """对话页的「我的账号」必须指向本页，且走 embed 路由而非门户路由。"""
    chat = CHAT.read_text(encoding="utf-8")
    m = re.search(r"const runHeaderMoreAccount = \(\) => \{(.*?)\n\};", chat, re.S)
    assert m, "对话页缺少 runHeaderMoreAccount"
    assert 'router.push({ name: "EmbedPersonal" })' in m.group(1), (
        "对话页未跳转到 /embed/personal"
    )
    assert "/dashboard/personal" not in m.group(1), (
        "跳到了门户路由——嵌入场景会被守卫拦到登录页"
    )


def test_return_entry_is_conditional_on_coming_from_chat():
    """返回键只在「从 /embed/chat 跳进来」时出现，不能无条件显示。"""
    view = _view()

    assert 'v-if="backToChat"' in view, "返回按钮未做条件渲染"

    m = re.search(r"const detectBackToChat = \(\) => \{(.*?)\n\};", view, re.S)
    assert m, "缺少 detectBackToChat"
    body = m.group(1)
    assert "history.state" in body, "未读取 history.state.back，无法判断来源"
    assert 'startsWith("/embed/chat")' in body, "未按 /embed/chat 前缀判断来源"
    assert "history.length" not in body, "用 history.length 判断来源不可靠——iframe 里也会 > 1"

    assert "onMounted(detectBackToChat)" in view, "未在挂载后判定来源"


def _return_button_tag() -> str:
    """取出返回按钮的开标签，供各条定位 / 可见性断言复用。"""
    view = _view()
    idx = view.index('v-if="backToChat"')
    start = view.rindex("<button", 0, idx)
    return view[start:view.index(">", idx)]


def test_return_entry_is_fixed_out_of_flow():
    """返回键必须 fixed：本页约定「只出现个人中心本身」，不该占布局、不该随滚动移出视口。"""
    tag = _return_button_tag()
    assert "fixed" in tag, "返回键未使用 fixed 定位"
    assert "absolute" not in tag, "返回键用了 absolute——容器滚动时会移出视口"
    assert 'aria-label="返回对话"' in tag, "返回键缺少可访问名称"


def test_return_entry_is_anchored_bottom_right():
    """必须落在右下角：放左上角会压住个人中心的 tab 栏（我的权限 / 我的记忆 / 我的 Token…）。"""
    tag = _return_button_tag()
    assert "bottom-4" in tag and "right-4" in tag, "返回键未锚定右下角"
    assert "top-3" not in tag, "返回键仍在顶部，会遮挡 tab 栏"
    assert "left-3" not in tag, "返回键仍在左侧，会遮挡 tab 栏"


def test_return_entry_is_mobile_only():
    """宽屏（Web）下不显示：此页有完整导航可回退，浮标纯属多余。

    断点用 sm:hidden（640px），与 EmbedChat 的 isMobile 口径一致。
    """
    tag = _return_button_tag()
    assert "sm:hidden" in tag, "返回键未在 ≥640px 隐藏，Web 下会多出浮标"


def test_return_entry_is_readable_over_content():
    """浮层压在内容之上，必须有实底 + 与正文的可见边界，否则底下的字透出来糊成一片。

    初版用 bg-white/70 半透明 + text-gray-400，用户反馈「是不是有点看不清」。
    浮层控件的可读性优先于「低调」。
    按用户偏好不用边框（bg-white/90），因此 shadow-sm 是**唯一**的分隔手段，不能一起删。
    """
    tag = _return_button_tag()
    assert "bg-white/90" in tag, "返回键背景过透，会与内容糊在一起"
    assert "text-gray-400" not in tag, "返回键文字过浅，压在内容上读不清"
    assert "shadow-sm" in tag, "返回键与正文缺少可见边界（已去边框，阴影是唯一分隔手段）"
    assert "border" not in tag, "返回键按用户偏好不用边框"


def test_return_entry_avoids_loud_accent():
    """但要克制：不用强调色实底、不用粗体，避免抢内容注意力。

    「低调」= 不用强调色，而不是降可读性。
    """
    tag = _return_button_tag()
    assert "bg-primary" not in tag, "返回键用了 primary 实底，过于抢眼"
    assert "font-bold" not in tag, "返回键用了粗体，拉高了视觉权重"
    assert "hover:" in tag, "返回键缺少 hover 提亮"


def test_return_entry_meets_touch_target():
    """浮标必须达到 44px 触控热区。

    它是移动端**唯一**的返回入口；初版为「低调」写成 text-xs + py-1.5，
    实际高度仅约 26px，与头部按钮 44px 的标准自相矛盾。
    「低调」不该降尺寸。
    """
    tag = _return_button_tag()
    assert "min-h-11" in tag, "返回键未达 44px 触控热区下限"
    assert "text-xs" not in tag, "返回键文字过小"
    assert "py-1.5" not in tag, "返回键用 py-1.5 撑高度，实际不足 44px"


def test_return_uses_history_back():
    """返回要走 history 回退，把用户送回原对话而不是新建一次导航。"""
    view = _view()
    m = re.search(r"const goBackToChat = \(\) => \{(.*?)\n\};", view, re.S)
    assert m, "缺少 goBackToChat"
    assert "router.back()" in m.group(1), "未使用 router.back()"
