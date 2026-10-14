"""管理页「?」引导弹层的遮罩必须铺满视口（Teleport 到 body + 足够高的层级）。

背景（一次真实排查）：多个管理页标题旁都有「?」引导弹层，写法是
`fixed inset-0 z-50`，看起来该铺满视口，但用户截图里遮罩只盖住了内容区——
顶部导航栏与左侧边栏都没被压暗。

用等价的 Tailwind 结构实测确认了机制：**只要祖先链上存在 transform**
（哪怕值看起来无害，比如 `translateY(0px)`），`position: fixed` 的包含块就从视口
变成那个祖先，遮罩随之只覆盖它。实测数据（视口 800）：

    遮罩留在内容区内（祖先带 transform）→ top=48, height=752   ← 与截图一致
    遮罩 Teleport 到 body               → top=0,  height=800   ✅

而 Dashboard.vue 的页面过渡恰好有：

    .page-enter-from { opacity: 0; transform: translateY(4px); }

在 `<transition name="page">` 套 `<Suspense>` 套异步路由组件的组合下，这个类在页面
稳定后不保证已被清理——于是「点 ? 就遮不满」。修法不是去追某一个祖先，而是把弹层
Teleport 到 body（项目里已有此约定），从此不受任何祖先的 transform / filter /
stacking context 影响。

这些断言守的是两件以后很容易被复制粘贴破坏的事：包裹层与层级。
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
VIEWS = ROOT / "frontend/src/views"
DASHBOARD = (VIEWS / "Dashboard.vue").read_text(encoding="utf-8")

#: 引导 / 规格弹层：页面内标题旁的「?」打开的那一层
GUIDE_OVERLAYS = {
    "TaskCenter.vue": "showSpecsModal",
    "KnowledgeBaseManagement.vue": "showHelp",
    "AgentManagement.vue": "showHelp",
    "McpManagement.vue": "showHelp",
    "ExampleManagement.vue": "showHelp",
    "SkillsManagement.vue": "showHelpModal",
}


def _source(filename: str) -> str:
    return (VIEWS / filename).read_text(encoding="utf-8")


@pytest.mark.parametrize("filename, variable", sorted(GUIDE_OVERLAYS.items()))
def test_guide_overlay_is_teleported_to_body(filename: str, variable: str):
    """弹层必须挂在 body 下：留在内容区内就会被祖先的 transform 改掉包含块。"""
    src = _source(filename)
    marker = f'v-if="{variable}"'
    assert marker in src, f"{filename} 里找不到引导弹层 {variable}"

    idx = src.index(marker)
    before = src[max(0, idx - 300) : idx]
    assert '<Teleport to="body">' in before, (
        f"{filename} 的引导遮罩没有 Teleport 到 body，"
        "祖先一旦带上 transform，遮罩就会只盖住内容区"
    )


@pytest.mark.parametrize("filename, variable", sorted(GUIDE_OVERLAYS.items()))
def test_guide_overlay_clears_all_layout_layers(filename: str, variable: str):
    """层级必须高于布局层：顶栏 z-30、移动端遮罩 z-40、侧边栏 z-50。

    停在 z-50 就与侧边栏同层——谁在上面只由 DOM 顺序决定，太脆弱。
    """
    src = _source(filename)
    idx = src.index(f'v-if="{variable}"')
    window = src[idx : idx + 200]
    assert "fixed inset-0 z-[100]" in window, f"{filename} 的引导遮罩层级应为 z-[100]"
    assert "fixed inset-0 z-50" not in window


def test_dashboard_chrome_layers_stay_below_the_overlay():
    """把布局层的实际层级钉住，避免有人把它们提到 100 以上反过来盖住弹层。"""
    for layer in ("z-30", "z-40", "z-50"):
        assert layer in DASHBOARD, f"Dashboard 布局层的 {layer} 变了，需复核弹层层级"


# --------------------------------------------------------------------------- #
# 全项目规则：同类写法一次性收敛（2026-10-02 排查时还剩 62 处）
# --------------------------------------------------------------------------- #

#: Tailwind 的等价写法：`z-50` 与 `z-[50]` 落地是同一个层级；中间还可能夹着
#: `overflow-hidden` 一类修饰类。用正则而不是字面量匹配，否则等价写法会漏网。
_OVERLAY_ON_LAYOUT_LAYER = re.compile(r"fixed inset-0[^\"'<>]*z-(?:50|\[50\])")


def test_no_overlay_left_on_the_layout_layer():
    """全项目不许再出现停在布局层（`z-50` / `z-[50]`）的弹层遮罩。

    它和侧边栏（z-50）同层——谁在上面只由 DOM 顺序决定；又不在 Teleport 内，
    祖先一旦带上 transform 就遮不满。新增弹层请照抄 `Teleport` + `z-[100]`。
    布局自己的层级（如顶栏 z-30、移动端遮罩 z-40、侧边栏 z-50）不受此约束。

    2026-10-08 补漏：原规则只匹配字面量 `fixed inset-0 z-50`，于是
    `AgentVersionsDrawer.vue` 的 `fixed inset-0 overflow-hidden z-[50]`
    （等价写法 + 中间夹类）成了唯一漏网之鱼，用户再次截图反馈「遮罩没铺满」。
    """
    offenders = []
    for path in sorted((ROOT / "frontend/src").rglob("*.vue")):
        text = path.read_text(encoding="utf-8")
        for match in _OVERLAY_ON_LAYOUT_LAYER.finditer(text):
            line = text[: match.start()].count("\n") + 1
            offenders.append(f"{path.relative_to(ROOT)}:{line}: {match.group(0)}")

    assert not offenders, f"这些弹层遮罩仍停在布局层，请改为 Teleport + z-[100]: {offenders}"


def test_every_full_screen_overlay_sits_inside_a_teleport():
    """每一个 `fixed inset-0 z-[100]` 遮罩，它之前必须有一个尚未闭合的 `<Teleport>`。

    只把层级改高、忘了 Teleport 是很自然的疏漏（批量替换尤其容易漏），
    所以单独守一条：层级对了不等于位置对了。
    用「到该位置为止 Teleport 标签的开、闭净数」来判断，对嵌套弹层同样成立。
    """
    missing = []
    for path in (ROOT / "frontend/src").rglob("*.vue"):
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"fixed inset-0 z-\[100\]", text):
            line_start = text.rfind("\n", 0, match.start()) + 1
            line_end = text.find("\n", match.start())
            line = text[line_start : line_end if line_end != -1 else len(text)]
            # `:class="{ 'fixed inset-0 z-[100] ...': isFullscreen }"` 是布局的全屏切换，
            # 不是弹层遮罩，也不该被 teleport（它必须留在原来的容器里）。
            if ":class" in line:
                continue
            prefix = text[: match.start()]
            if prefix.count("<Teleport") <= prefix.count("</Teleport>"):
                missing.append(f"{path.relative_to(ROOT)}:{prefix.count(chr(10)) + 1}")
    assert not missing, f"这些遮罩只提了层级、没有 Teleport 到 body: {missing}"


# --------------------------------------------------------------------------- #
# 业务弹窗遮罩：带遮罩背景色的全屏弹层（z ≥ 100）同样必须 Teleport 到 body
#
# 2026-10-13 排查：角色管理页「编辑角色」弹窗的遮罩又一次没铺满（用户第三次
# 反馈同类问题）。根因与前两次相同——弹层留在内容区里，祖先一旦带上 transform
# （Dashboard 的 `.page-enter-from { transform: translateY(4px) }`）就改写了
# `position: fixed` 的包含块，遮罩只盖得住内容区。
#
# 前两次修复之所以没覆盖到它，是因为契约的判据只认 `z-50` / `z-[50]` / `z-[100]`
# 这几个字面层级，而系统管理页（角色管理、用户管理）的业务弹窗用的是
# `bg-black bg-opacity-50 ... z-[9990]` 这一套——层级够高，位置仍然在内容区里。
#
# 判据放宽到「带遮罩背景色 + z ≥ 100」：层级够高只说明盖得住布局层，
# 与「是否挂在 body 下」是两件事，后者才是遮罩能不能铺满视口的决定因素。
# --------------------------------------------------------------------------- #

#: `fixed inset-0` 的全屏层容器（静态 class，动态 :class 不在此列）
_MASKED_OVERLAY = re.compile(r'(?<!:)class="([^"]*\bfixed\b[^"]*\binset-0\b[^"]*)"')
#: 遮罩色只作参考，**不再**是判据：技能详情抽屉把蒙层写成内层
#: `absolute inset-0 bg-black/30`，外层容器只有
#: `fixed inset-0 z-[9950] overflow-hidden`，
#: 于是"带遮罩色"这一条把它整条漏掉——第 4 次同类问题就出在这里。决定遮罩能否铺满的
#: 是「是否挂在 body 下」，与颜色写在哪一层无关。
#: 所以判据只看 `fixed inset-0` + z ≥ 100。
_MASKED_BG = re.compile(r"bg-(?:black|gray-\d+|slate-\d+)")

#: components/ 下尚未收敛的历史遗留（抽屉/面板内的弹层，层级依赖需单独评估）。
#: 棘轮语义：只允许减少，不允许新增；修掉一处就把它从清单里删掉。
#:
#: 这份清单曾被虚报过两次，都是判据自身的毛病，记录在此以免重蹈：
#:   1. 只认大写 `<Teleport`，而 Vue 两种写法都合法——chatbi/embed/knowledge 下
#:      多个已经在 `<teleport>` 内的抽屉被误判成漏网，虚增 15 条；
#:   2. 把 `v-if="isResizing"` + `cursor-col-resize` 的拖拽守护层当成遮罩——那是
#:      拖拽时屏蔽 iframe/文本选择的透明拦截层，没有蒙层，不该 Teleport，虚增 6 条。
#: 修正后真实存量 6 条。
_PENDING_MASKED_OVERLAYS = {
    "frontend/src/components/SessionTraceModal.vue:39",
    "frontend/src/components/ThirdPartyUserSyncDrawer.vue:4",
    "frontend/src/components/ThirdPartyUserSyncDrawer.vue:443",
    "frontend/src/components/data-portal/DataPortalReportCreateModal.vue:921",
    "frontend/src/components/data-portal/DataPortalReportCreateModal.vue:1288",
    "frontend/src/components/embed/WorkspaceDirectorySaveDialog.vue:114",
}


def _unteleported_masked_overlays(paths):
    """返回「全屏层（`fixed inset-0` 且 z ≥ 100）但不在 Teleport 内」的 `文件:行号` 列表。

    不要求自带遮罩色：技能详情抽屉把蒙层写在内层 `absolute inset-0 bg-black/30`，
    外层容器是裸的，按颜色找会整条漏掉。
    """
    offenders = []
    for path in sorted(paths):
        text = path.read_text(encoding="utf-8")
        for match in _MASKED_OVERLAY.finditer(text):
            cls = match.group(1)
            z = re.search(r"\bz-\[?(\d+)\]?", cls)
            if not z or int(z.group(1)) < 100:
                continue
            # 拖拽守护层：`v-if="isResizing"` + `cursor-col-resize` 的透明拦截层，
            # 用于拖拽时屏蔽 iframe/文本选择，没有蒙层、不承担遮挡职责。
            if "cursor-col-resize" in cls or "cursor-row-resize" in cls:
                continue
            prefix = text[: match.start()]
            # `Teleport` 与 `teleport` 都是合法写法，必须大小写不敏感地统计——
            # 此前只认大写，把 chatbi/embed/knowledge 下 5 个已在 `<teleport>` 内的
            # 抽屉误判成漏网（虚报了 5 处存量）。
            if len(re.findall(r"<[Tt]eleport\b", prefix)) > len(
                re.findall(r"</[Tt]eleport>", prefix)
            ):
                continue
            offenders.append(f"{path.relative_to(ROOT)}:{prefix.count(chr(10)) + 1}")
    return offenders


def test_masked_dialog_overlays_in_views_are_teleported():
    """views/ 下所有全屏层都必须 Teleport 到 body。

    这些弹层直接渲染在 Dashboard 的 `<main>` 内，祖先链上只要出现 transform
    （页面过渡的 `.page-enter-from` 就是），遮罩就只盖得住内容区：
    顶部导航栏与左侧边栏压不暗——用户看到的正是这个现象。
    层级停在 z-[9990] 并不能解决，因为包含块已经被改掉了。
    """
    offenders = _unteleported_masked_overlays((ROOT / "frontend/src/views").glob("*.vue"))
    assert not offenders, (
        "这些业务弹窗遮罩没有 Teleport 到 body，祖先一旦带上 transform 就遮不满视口，"
        f"请照抄 `Teleport to=\"body\"` 的既有写法: {offenders}"
    )


def test_no_new_unteleported_masked_overlay_in_components():
    """components/ 下的同类漏网只减不增（历史遗留见 `_PENDING_MASKED_OVERLAYS`）。"""
    current = set(_unteleported_masked_overlays((ROOT / "frontend/src/components").rglob("*.vue")))
    added = sorted(current - _PENDING_MASKED_OVERLAYS)
    assert not added, (
        f"新增了没有 Teleport 的全屏遮罩弹层: {added}；"
        "新增弹层请用 `<Teleport to=\"body\">` 包裹"
    )
    fixed = sorted(_PENDING_MASKED_OVERLAYS - current)
    assert not fixed, f"这些遮罩已经修好了，请从 _PENDING_MASKED_OVERLAYS 清单里删掉: {fixed}"
