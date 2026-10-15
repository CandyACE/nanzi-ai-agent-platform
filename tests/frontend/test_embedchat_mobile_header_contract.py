"""EmbedChat 移动端头部收纳契约测试。

背景：移动端（< 640px）头部原有 4 个 32px 图标并排——占宽 152px，在 375px 屏上
吃掉 40% 的宽度，既挤压标题（标题已被迫挂 truncate），又低于 44px 触控热区下限，
误触率高。

收敛后：移动端头部**只留「更多」一个按钮**（44px 热区）；设置 / 快捷指令 / 帮助 /
服务端浏览器全部收进「更多」——形态是**锚定弹层**（与输入区「+」弹层同形态、紧凑单行），
**不是底部抽屉**。

只做源码静态断言（沿用 tests/frontend 既有风格），不启动浏览器。
"""

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.no_infrastructure

ROOT = Path(__file__).resolve().parents[2]
VIEW = ROOT / "frontend/src/views/EmbedChat.vue"

# 收进「更多」弹层、因而对移动端隐藏的入口
MENU_ONLY_LABELS = ["Settings Button", "Help Button", "Server Browser Button"]


def _view() -> str:
    return VIEW.read_text(encoding="utf-8")


def _container_tag_after(view: str, marker: str) -> str:
    """取某段注释标记之后第一个 <div ...> 开标签（即该按钮的容器）。"""
    idx = view.index(marker)
    start = view.index("<div", idx)
    end = view.index(">", start)
    return view[start:end]


def test_view_exists():
    assert VIEW.exists(), f"缺少视图文件: {VIEW}"


def test_menu_only_entries_are_hidden_on_mobile():
    """帮助 / 服务端浏览器必须对移动端隐藏，否则收纳没发生。"""
    view = _view()
    for label in MENU_ONLY_LABELS:
        tag = _container_tag_after(view, f"<!-- {label}")
        assert 'v-if="!isMobile"' in tag, f"{label} 未对移动端隐藏，仍会占用头部宽度"


def test_settings_moves_into_menu_on_mobile():
    """设置也收进弹层：移动端头部只留「更多」一个按钮，设置不再单独占位。"""
    view = _view()
    tag = _container_tag_after(view, "<!-- Settings Button")
    assert 'v-if="!isMobile"' in tag, "设置未对移动端隐藏，仍在头部单独占位"

    # 不依赖固定字符窗口：设置图标的 SVG path 本身就接近 700 字符，窗口法会误判。
    start = view.index('@click="runHeaderMoreSettings"')
    end = view.index("</transition>", start)
    assert "对话设置" in view[start:end], "弹层里缺少「对话设置」入口——设置就没有移动端入口了"


def test_shortcuts_moves_into_menu_on_mobile():
    """快捷指令在移动端进弹层；桌面上仅作为「重新打开快捷指令」的入口存在。"""
    view = _view()
    tag = _container_tag_after(view, "<!-- Shortcuts Button")
    assert 'v-if="!isMobile"' in tag, "快捷指令未对移动端隐藏，应改由弹层进入"
    assert "!config.showShortcuts" in view, "桌面端缺少快捷指令的重新打开入口"


def test_desktop_entrypoints_are_kept():
    """收纳不等于删除：三个入口的点击处理器必须仍在（桌面端继续直接可用）。"""
    view = _view()
    for handler in (
        '@click="handleHeaderShortcutsClick"',
        '@click="showHelpModal = true"',
        '@click="toggleBrowserPanel"',
    ):
        assert handler in view, f"入口丢失: {handler}"


def test_more_button_is_mobile_only_and_meets_touch_target():
    """「更多」按钮仅移动端出现，且热区达到 44px（min-h-11/min-w-11）。"""
    view = _view()
    idx = view.index('@click="toggleHeaderMore"')
    start = view.rindex("<button", 0, idx)
    end = view.index(">", idx)
    tag = view[start:end]

    assert "min-h-11" in tag and "min-w-11" in tag, "「更多」按钮热区未达 44px"
    assert 'aria-haspopup="menu"' in tag, "「更多」按钮缺少 aria-haspopup"
    assert ':aria-expanded="showHeaderMore"' in tag, "「更多」按钮缺少 aria-expanded 状态"


def test_more_menu_is_anchored_popover_not_bottom_sheet():
    """必须是贴着按钮展开的锚定弹层，而不是贴底抽屉。"""
    view = _view()

    match = re.search(r'<div v-if="showHeaderMore" class="([^"]*)"', view)
    assert match, "未找到「更多」弹层容器"
    cls = match.group(1)
    assert "absolute" in cls, "弹层未使用绝对定位（无法贴按钮）"
    assert "top-full" in cls and "right-0" in cls, "弹层未锚定在按钮下方右侧"
    assert "inset-x-0" not in cls and "bottom-0" not in cls, "弹层退化成了贴底抽屉"

    assert not re.search(r"<MobileActionSheet[^>]*showHeaderMore", view, re.S), (
        "「更多」不应再使用底部抽屉壳"
    )


def test_more_menu_closes_on_outside_click():
    """点弹层外部要能关闭，且不能把弹层内部的点击也当外部。"""
    view = _view()

    m = re.search(r"const handleHeaderMoreGlobalClick = \(event: MouseEvent\) => \{(.*?)\n\};", view, re.S)
    assert m, "缺少全局点击处理"
    body = m.group(1)
    assert "headerMoreRef.value.contains" in body, "未做 contains 判定，点弹层内部也会被关掉"
    assert "showHeaderMore.value = false" in body, "外部点击未关闭弹层"

    assert "document.addEventListener('click', handleHeaderMoreGlobalClick)" in view
    assert "document.removeEventListener('click', handleHeaderMoreGlobalClick)" in view, (
        "监听未卸载，组件销毁后会泄漏"
    )


def test_menu_actions_close_menu_before_acting():
    """弹层内动作必须先关弹层再触发原动作，否则 modal 会叠在弹层之上。"""
    view = _view()
    for fn_name, action in [
        ("runHeaderMoreSettings", "showSettings.value = true"),
        ("runHeaderMoreShortcuts", "handleHeaderShortcutsClick()"),
        ("runHeaderMoreHelp", "showHelpModal.value = true"),
        ("runHeaderMoreBrowser", "toggleBrowserPanel()"),
        ("runHeaderMoreAccount", 'router.push({ name: "EmbedPersonal" })'),
    ]:
        m = re.search(rf"const {fn_name} = \(\) => \{{(.*?)\n\}};", view, re.S)
        assert m, f"缺少 {fn_name}"
        body = m.group(1)
        assert "closeHeaderMore()" in body, f"{fn_name} 未先关闭弹层"
        assert action in body, f"{fn_name} 未触发原动作"
        assert body.index("closeHeaderMore()") < body.index(action), f"{fn_name} 应先关弹层再执行动作"


def test_menu_is_compact_single_line():
    """弹层走紧凑单行：w-52 宽、无副标题（与输入区「+」弹层同一密度）。"""
    view = _view()

    m = re.search(r'<div class="(w-\d+) rounded-xl border border-gray-200 bg-white py-1\.5 shadow-xl', view)
    assert m, "未找到「更多」弹层面板"
    assert m.group(1) == "w-52", f"弹层未使用紧凑宽度 w-52（当前 {m.group(1)}）"

    start = view.index("@click=\"runHeaderMoreSettings\"")
    end = view.index("</transition>", start)
    assert "text-[11px]" not in view[start:end], "弹层里仍有副标题，不够紧凑"


def test_account_entry_opens_embed_personal_not_portal():
    """「我的账号」必须跳 embed 个人中心，不能跳门户的 /dashboard/personal。

    门户路由 meta.public 为 false，嵌入场景（iframe / 小程序 web-view）下会被守卫
    拦到登录页；/embed/personal 与之同 layout 且 public，可直接 SPA 内切换。
    """
    view = _view()
    assert "我的账号" in view, "弹层里缺少「我的账号」入口"

    m = re.search(r"const runHeaderMoreAccount = \(\) => \{(.*?)\n\};", view, re.S)
    assert m, "缺少 runHeaderMoreAccount"
    body = m.group(1)
    assert 'router.push({ name: "EmbedPersonal" })' in body, "未跳转到 /embed/personal"
    assert "/dashboard/personal" not in body, "跳到了门户路由，嵌入场景会被守卫拦走"


def test_breakpoint_change_closes_more_menu():
    """跨过 640px 断点必须收起弹层，否则状态会悬空。"""
    view = _view()
    m = re.search(r"if \(wasMobile !== isMobile\.value\) \{(.*?)\}", view, re.S)
    assert m, "未找到断点判断"
    assert "closeHeaderMore()" in m.group(1), "跨断点未收起「更多」弹层"
    assert "closeMobileActions()" in m.group(1), "跨断点未收起消息操作抽屉（回归）"


def test_badge_surfaces_state_hidden_by_the_menu():
    """收起后状态不能丢：设置的反幻觉校验 / 服务端浏览器已打开，都要能透出提示。"""
    view = _view()
    m = re.search(r"const headerMoreBadge = computed\(\(\) => (.*?)\);", view, re.S)
    assert m, "缺少 headerMoreBadge"
    expr = m.group(1)
    assert "browserPanelVisible" in expr, "未透出「服务端浏览器已打开」状态"
    assert "enableGrounding" in expr, "未透出「反幻觉校验已开启」状态"
