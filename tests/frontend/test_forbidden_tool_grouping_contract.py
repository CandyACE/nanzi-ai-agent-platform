"""禁用工具分组渲染的前端接线契约（spec §4 的第 10～13 项）。

组件只该做三件事：渲染三层结构、维护两级折叠状态、把事件转发给纯函数。
聚合 / 计数 / 全选 / 过滤一旦在组件里被重新实现一份，就会和纯函数悄悄漂移
——这几条断言就是钉住"委托"这件事。
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPONENT = (ROOT / "frontend/src/components/system/ForbiddenToolCatalog.vue").read_text(
    encoding="utf-8"
)
UTILS = (ROOT / "frontend/src/utils/forbiddenToolGroups.ts").read_text(encoding="utf-8")


def test_component_renders_three_levels_with_two_level_collapse_and_search():
    """大组 → 子组 → 卡片；大组键 group:builtin / group:dynamic，子组键用 group_key。

    搜索期间只读强制展开（不写回折叠集合）；无命中的大组整组隐藏，内置区同样适用。
    """
    assert "GROUP_BUILTIN_KEY = 'group:builtin'" in COMPONENT
    assert "GROUP_DYNAMIC_KEY = 'group:dynamic'" in COMPONENT
    assert "toggleCollapse(GROUP_BUILTIN_KEY)" in COMPONENT
    assert "toggleCollapse(GROUP_DYNAMIC_KEY)" in COMPONENT
    assert "toggleCollapse(sub.key)" in COMPONENT, "子组折叠键必须是后端给的 group_key"
    # 与 AgentVersionEditorDrawer 一致的分组头语言：rotate-90 过渡 + (已选/总数) + 全选按钮
    assert "transition-transform" in COMPONENT and "rotate-90" in COMPONENT
    assert "{{ selectedCountOf(sub.candidates) }}/{{ sub.candidates.length }}" in COMPONENT
    assert "'取消全选' : '全选'" in COMPONENT

    assert "const isExpanded = (key: string) => isSearching.value || !collapsedKeys.value.has(key)" in COMPONENT
    assert "filterSubGroups(builtinGroups.value, searchQuery.value)" in COMPONENT
    assert "filterSubGroups(dynamicGroups.value, searchQuery.value)" in COMPONENT
    # 内置大组过去恒显示，这次也要遵守"无命中则隐藏"
    assert "showBuiltinSection" in COMPONENT
    assert "visibleBuiltinGroups.value.length > 0" in COMPONENT
    assert "showDynamicSection" in COMPONENT
    assert "搜索状态下分组自动展开，清空搜索后可折叠" in COMPONENT

    # 折叠集合的写入口只有 toggleCollapse，且它不看搜索状态（搜索只是只读覆盖）
    toggle_body = COMPONENT.split("const toggleCollapse = (key: string) => {")[1].split("}")[0]
    assert "isSearching" not in toggle_body
    assert COMPONENT.count("collapsedKeys.value = next") == 1


def test_dynamic_group_has_no_inner_scroll_region():
    """大组 2 去掉内滚动：长度交给子组折叠，极端情况由页面整体滚动承担。"""
    assert "max-h-[140px]" not in COMPONENT
    assert "overflow-y-auto" not in COMPONENT


def test_orphan_section_stays_independent_and_unfiltered():
    """orphan 区独立渲染：不被搜索过滤、不参与折叠与大组全选、加载失败时仍渲染。"""
    assert "其他已禁用项（历史）" in COMPONENT
    assert "bg-amber-50/40" in COMPONENT
    # orphan 判定委托纯函数：只有"目录里完全查不到"的名字才算历史遗留，
    # 勾选写入的整组别名（write_file → edit_file/apply_patch）必须留在原分组里。
    assert "findOrphanIds(" in COMPONENT

    orphan_block = COMPONENT.split("历史遗留：已禁用但已不在目录中的工具")[1].split("</template>")[0]
    assert "isExpanded" not in orphan_block, "orphan 区不参与折叠"
    assert "searchQuery" not in orphan_block, "orphan 区不被搜索过滤"
    assert "toggleSelection(orphanIds" not in COMPONENT, "orphan 不参与大组全选"
    assert "toggleOrphan" in orphan_block

    # 加载失败时 orphan 区照旧渲染：两者是并列的顶层区块，不是互斥分支
    assert 'v-if="orphanIds.length"' in COMPONENT
    assert 'v-else-if="loadError"' in COMPONENT


def test_component_delegates_grouping_to_pure_functions():
    """组件只引用纯函数，不在内部重写聚合 / 过滤 / 计数。"""
    assert "from '../../utils/forbiddenToolGroups'" in COMPONENT
    for helper in ("groupCandidates(", "groupSelectedCount(", "applyGroupSelection(", "filterSubGroups("):
        assert helper in COMPONENT, f"组件必须委托 {helper}"

    # 反向断言：这些是纯函数的职责，组件里出现就说明又写了一套
    assert "new Map(" not in COMPONENT, "聚合不该在组件里重写"
    assert ".toLowerCase()" not in COMPONENT, "大小写不敏感匹配属于 filterSubGroups"
    assert "aliases.some(" not in COMPONENT, "aliases 命中判定属于 groupSelectedCount"

    # 纯函数模块本身要导出 spec §3.4 的四个函数与两个接口
    for exported in (
        "export function groupCandidates(",
        "export function groupSelectedCount(",
        "export function applyGroupSelection(",
        "export function filterSubGroups(",
        "export interface ForbiddenToolCandidate",
        "export interface ForbiddenToolSubGroup",
    ):
        assert exported in UTILS, f"forbiddenToolGroups.ts 缺少 {exported}"

    # 标签与归属由后端决定：前端不得维护类别中文映射
    assert "沙箱命令" not in UTILS
    assert "MCP · " not in UTILS


def test_selected_groups_are_toned_red_without_bleeding_into_items_or_orphans():
    """组卡片由色调映射决定红化；候选条目与 orphan 区必须保持原样。"""
    source = COMPONENT

    assert "groupToneClasses" in source, "色调应由纯函数决定，不在模板里散落三元"
    # 两个大组 + 两处子分组，都要走同一个入口
    assert source.count("toneOf(") >= 4, "大组/子分组未全部接入色调映射"
    assert "toneOf(builtinVisibleCandidates, 'gray')" in source
    assert "toneOf(dynamicVisibleCandidates, 'indigo')" in source

    # 候选条目保持中性白底：红化只发生在"组"这一层，否则红成一片看不清勾了哪项
    # 两处组的候选条目 + orphan 区条目，三处都保持中性白底
    assert source.count("rounded border bg-white") == 3

    # orphan 区（琥珀色）不参与色调映射
    orphan_block = source.split("历史遗留：已禁用但已不在目录中的工具")[1].split("</template>")[0]
    assert "toneOf(" not in orphan_block
    assert "bg-amber-50/40" in source
