"""智能体级资源限制的界面契约：入口可见性、弹框行为、payload 口径。

入口口径（与产品确认）：
  - 入口只在**权限配置 → 数据资产 → 智能体**卡片的右侧；
  - 只在**已勾选（已授权）**的智能体上出现——没分配就不必配；
  - 已授权且有限制时显示已禁数量角标。

弹框口径：
  - 分组来自接口（内置工具 / 自定义 API 工具 / MCP 按 server / 公共技能 / 个人技能），
    **绑什么才有什么，不硬编码组数**；
  - 已全局禁用的项置灰 + 「已全局禁用」+ 不可勾选（排除只增不减）；
  - 保存只提交该智能体的两项限制，且路径/计数/判定全部复用 agentRestrictions.ts。
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
USERS = Path("frontend/src/views/Users.vue")
ROLES = Path("frontend/src/views/Roles.vue")
DIALOG = Path("frontend/src/components/system/AgentRestrictionDialog.vue")
UTILS = Path("frontend/src/utils/agentRestrictions.ts")
CACHE = Path("frontend/src/utils/agentRestrictionCache.ts")


def _source(path: Path) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


# 两页必须一字不差地使用同一段可见性条件：口径漂移过一次（角色页曾用另一种写法）
VISIBILITY_CONDITION = (
    "v-if=\"activeResTab === 'agents' && (permissionData as any).agents.includes(res.id)\""
)


def test_utils_module_exists_and_is_the_single_place_for_paths():
    source = _source(UTILS)

    assert "export function agentRestrictableResourcesPath(" in source
    assert "export function agentRestrictionPath(" in source
    assert "export function agentRestrictableCatalogCacheKey(" in source
    assert "/api/portal/management/agents" in source, (
        "智能体级限制挂在 management 下（后端实际路由见 management.py）"
    )

    for page in (USERS, ROLES):
        page_source = _source(page)
        assert "agent-restrictions" not in page_source, (
            f"{page} 不得自己拼接口路径（否则路径口径会出现第二份）"
        )
        assert "restrictable-resources" not in page_source
        assert "user_id=" not in page_source, f"{page} 不得自己拼视角参数"
        assert "utils/agentRestrictions" in page_source, f"{page} 必须复用共享判定模块"

    assert "agent-restrictions" in _source(UTILS)
    assert "restrictable-resources" in _source(UTILS)


def test_entry_button_only_shows_on_checked_agent_cards():
    for page in (USERS, ROLES):
        source = _source(page)

        assert VISIBILITY_CONDITION in source, (
            f"{page} 的「功能限定」入口必须同时满足「在智能体卡片上」与「该智能体已勾选」"
        )
        assert ">功能限定<" in source or "功能限定" in source
        assert "@click.stop.prevent=\"openAgentRestriction(res)\"" in source, (
            f"{page} 的入口必须阻止冒泡，否则点按钮会顺手切换勾选态"
        )
        assert '<AgentRestrictionDialog' in source, f"{page} 未接入弹框组件"
        assert 'v-model="showAgentRestrictionDialog"' in source
        assert '@saved="onAgentRestrictionSaved"' in source, (
            f"{page} 保存后必须回填角标计数，否则角标要等下次打开才更新"
        )


def test_entry_badge_uses_shared_counter():
    for page in (USERS, ROLES):
        source = _source(page)

        assert "agentRestrictionCount(res.id)" in source, f"{page} 的角标必须走共享计数"
        assert "countAgentRestrictionBadge(" in source, f"{page} 角标口径必须来自共享纯函数"


def test_entry_badge_loads_counts_in_one_batch_request():
    """角标必须走批量接口，而不是逐个智能体 GET。

    逐个 GET 会让打开一次权限页发出 N 个请求（N = 已授权智能体数）。更要紧的是口径：
    批量接口返回的是**清单**而非计数，角标才能复用 `countAgentRestrictionBadge` 剔除
    「全局已禁用」项——若后端直接给数字，就会出现"角标 3、打开只有 1 项"。
    """
    for page in (USERS, ROLES):
        source = _source(page)

        assert "agentRestrictionCountsPath(" in source, f"{page} 的角标必须走批量接口"
        assert "writeAgentRestriction(" in source, (
            f"{page} 批量结果要回填限制缓存，弹框随后打开即命中、不再多打一次"
        )
        # 逐个 GET 的写法（在计数流程里带上具体 agentId 的限制路径）必须消失
        assert not re.search(
            r"agentRestrictionPath\(\s*['\"](?:user|role)['\"]", source
        ), f"{page} 不应再逐个智能体请求限制清单"
        # 批大小常量属于"逐个并发"的实现痕迹，批量后不该存在
        assert "AGENT_RESTRICTION_COUNT_BATCH" not in source, (
            f"{page} 仍是分批并发的逐个请求实现"
        )


def test_scope_kind_matches_the_page():
    users = _source(USERS)
    roles = _source(ROLES)

    assert 'kind="user"' in users, "用户页的智能体限制作用域必须是 user"
    assert ':scope-id="editingUserId"' in users
    assert 'kind="role"' in roles, "角色页的智能体限制作用域必须是 role"
    assert ':scope-id="currentRole?.id ?? null"' in roles, (
        "角色弹框关闭后 currentRole 会置空，模板必须用可选链，否则会抛运行时错"
    )


def test_dialog_renders_groups_from_the_api_without_hardcoding_four_sections():
    source = _source(DIALOG)

    assert 'v-for="group in visibleGroupsOf(tab)"' in source, (
        "分组必须迭代接口返回的 groups（现在落在当前页签内）"
    )
    assert "v-for=\"tab in tabs\"" in source, "分组要被页签组织起来"
    for hardcoded in ("builtin_tools", "public_skills", "personal_skills"):
        assert hardcoded not in source, f"弹框硬编码了分组键 {hardcoded}（MCP 组数量不定）"
    assert "visibleGroups" in source
    assert "filterRestrictableGroups(" in source, "搜索必须复用共享过滤函数"


def test_dialog_marks_globally_forbidden_items_readonly():
    source = _source(DIALOG)

    assert "已全局禁用" in source, "全局禁用项必须有徽标说明为什么点不动"
    # 只读原因有两种：全局禁用（并集语义，本层无从放开）与不可限定（个人技能，
    # 运行时任何一处都不读）。二者共用同一处置灰/禁用判定，避免只覆盖一半。
    assert "item.forbidden_globally || item.not_restrictable" in source, (
        "全局禁用项必须置灰不可勾选"
    )
    assert "applyGroupRestrictionSelection(" in source, "全选/取消全选必须走共享纯函数"
    assert "groupSelectionState(" in source, "分区计数与「已全选」判定必须走共享纯函数"
    assert "sanitizeAgentRestrictionLists(" in source, (
        "回显要剔除全局禁用项，避免把全局项写成智能体级记录"
    )


def test_dialog_payload_only_ships_this_agents_restriction_lists():
    source = _source(DIALOG)

    assert "buildAgentRestrictionPayload(" in source, "payload 必须由共享纯函数构造"
    assert "forbidden_commands" not in source, "命令禁用不属于智能体级作用域"
    assert "agentRestrictionPath(" in source, "PUT/GET 路径必须来自共享构造函数"
    assert "agentRestrictableResourcesPath(" in source


def test_dialog_candidates_are_fetched_with_the_scope_perspective():
    """候选清单必须带视角参数并按键带视角缓存，否则全局禁用项不会置灰。"""
    source = _source(DIALOG)

    assert "agentRestrictableResourcesPath(props.kind, props.scopeId, agentId)" in source
    assert "agentRestrictableCatalogCacheKey(" in source
    assert "catalogCacheKey.value" in source, "候选清单加载必须用带视角的缓存键"
    assert "?user_id=" not in source and "?role_id=" not in source, (
        "视角参数只能由 agentRestrictableResourcesPath 拼，不得在组件里内联"
    )


def test_dialog_counts_come_from_the_shared_pure_functions():
    """「已选 N 项」与分区 (n/m) 都走共享计数：分母只算可勾选项，全局禁用项不计入。"""
    source = _source(DIALOG)

    assert "countAgentRestrictionBadge(" in source, (
        "底部「已选 N 项」必须与卡片角标同口径（countRestrictionEntries 只收数组，"
        "直接喂 {forbidden_tools, forbidden_skills} 会恒为 0）"
    )
    assert "countRestrictionEntries(" not in source
    assert "selectedCount" in source
    assert "({{ groupState(group).selected }}/{{ groupState(group).selectable }})" in source, (
        "分区计数必须用「可勾选数」当分母：把全局禁用项算进分母会让「全选」永远点不亮"
    )


def test_dialog_put_body_is_exactly_the_built_payload():
    """保存请求体只能是 buildAgentRestrictionPayload 的结果，不得内联拼接字段。"""
    source = _source(DIALOG)

    assert re.search(
        r"axios\.put\(\s*agentRestrictionPath\([^)]*\),\s*payload,?\s*\)",
        source,
    ), "PUT 的 body 必须是 payload（只含 forbidden_tools / forbidden_skills）"


def test_dialog_reuses_cache_and_error_extraction():
    source = _source(DIALOG)

    assert "loadAgentRestrictableCatalog(" in source, "候选清单要走按视角去重的缓存"
    assert "loadAgentRestriction(" in source, "已有配置走按 (作用域, 智能体) 去重的缓存"
    assert "writeAgentRestriction(" in source, "保存成功后回填缓存，避免再 GET 一次"
    assert "extractApiErrorDetail(" in source, "报错文案必须走共享提取函数"

    cache = _source(CACHE)
    assert "export function loadAgentRestriction(" in cache
    assert "export function loadAgentRestrictableCatalog(" in cache
    assert "agentRestrictions" in cache, "缓存模块必须复用共享归一化"


def test_dialog_offers_cleanup_for_unbound_history_items():
    source = _source(DIALOG)

    assert "findUnboundRestrictionIds(" in source
    assert "不再绑定" in source, "工具解绑/改名后要标注原因，并提供一键清理"
    assert "clearUnbound" in source


def test_views_do_not_reimplement_the_restriction_logic():
    for page in (USERS, ROLES):
        source = _source(page)
        # 判定/计数/路径一律来自 utils，页面里不得出现内联判定
        assert not re.search(r"forbidden_globally\s*\.", source), (
            f"{page} 内联了全局禁用项判定，应放在 agentRestrictions.ts"
        )
        assert "agentRestrictionCacheKey(" in source, f"{page} 必须用共享缓存键"


def test_dialog_shows_chinese_descriptions_instead_of_bare_ids():
    """条目副标题必须显示中文描述。

    改造前副标题固定是等宽 id，于是弹框里每个工具都是一行 `system_http_request`——
    管理员看不出这是什么工具；而智能体编辑页显示的一直是描述。
    """
    source = (
        ROOT / "frontend/src/components/system/AgentRestrictionDialog.vue"
    ).read_text(encoding="utf-8")

    assert "item.description || item.id" in source, "有描述显示描述，没有才退回 id"
    assert ":class=\"item.description ? '' : 'font-mono'\"" in source, (
        "中文描述不该用等宽字体；只有回退成 id 时才用"
    )


def test_dialog_explains_where_the_candidates_come_from():
    """弹框必须说明候选来源版本，以及"全局禁用项不计入可选数"。

    这两句直接回答管理员的疑问："为什么这里的数量和智能体编辑页不一样"。候选取自某个
    具体版本（优先已发布），而编辑页改的是草稿；全局禁用项又会从可选数里剔除。
    """
    source = (
        ROOT / "frontend/src/components/system/AgentRestrictionDialog.vue"
    ).read_text(encoding="utf-8")

    assert "sourceVersionLabel" in source
    assert "已全局禁用的项在列表里置灰，不计入页签的可选数量" in source
    assert "const sourceVersion = ref<AgentRestrictionSourceVersion | null>(null)" in source
    assert "sourceVersion.value = catalog.sourceVersion" in source
    # 来源版本要能区分"已发布"与"草稿"，否则解释不了运行时到底用哪份
    assert "已发布版本" in source and "尚未发布" in source


def test_scope_notice_is_listed_and_highlighted():
    """作用域说明必须分条 + 带高亮底色。

    之前挤成一段灰色小字，管理员会直接略过，进而误以为这个弹框改的是全局禁用配置。
    两条分别是「影响到谁」和「改不了了怎么办」，各自独立成行。
    """
    source = (
        ROOT / "frontend/src/components/system/AgentRestrictionDialog.vue"
    ).read_text(encoding="utf-8")

    # 底色由 indigo 信息色改为 red 警示色（与「禁用资源」页的提示同一套语气），
    # 并改为铺满整行 + 可折叠；呈现细节由 test_scope_hint_is_full_width_red_and_collapsible 覆盖。
    assert "border-red-200 bg-red-50" in source, "说明区要有高亮底色，不能只是灰字"
    assert "只对「{{ scopeNoun }} × 该智能体」生效" in source
    assert "已全局禁用的项在此只读，需到「禁用资源」里调整。" in source
    # 两条各自是独立段落，靠圆点分列，而不是一句连排
    assert source.count('<span class="shrink-0 font-bold">•</span>') >= 2, "两条说明要各自带圆点分列"


def test_dialog_marks_not_restrictable_items_readonly_with_reason():
    """个人技能必须置灰只读 + 标注原因。

    权限侧三处过滤全部排除个人技能，所以在此勾选是空转（能存、运行时不读）。
    界面上要同时做到三件事，缺一个管理员就会以为"禁了但没效果"：
      1. 与全局禁用项一样置灰、禁用 checkbox；
      2. 角标写明「不支持限定」（不是「已全局禁用」——原因不同）；
      3. 悬停给出原因文案。
    """
    source = _source(DIALOG)

    assert "item.not_restrictable" in source, "模板必须识别不可限定标记"
    assert "不支持限定" in source, "角标文案要与「已全局禁用」区分"
    assert "not_restrictable_reason" in source, "原因文案要展示出来"
    assert (
        "item.forbidden_globally || item.not_restrictable" in source
    ), "置灰、禁用 cursor、禁用 checkbox 三处必须同时覆盖两种只读原因"
    # 角标顺序：不可限定优先（同名个人技能可能两者皆为真，此时本质原因是不支持限定）
    assert source.index("v-if=\"item.not_restrictable\"") < source.index(
        "v-else-if=\"item.forbidden_globally\""
    ), "不可限定角标要排在「已全局禁用」之前"


def test_dialog_reads_restrictability_from_shared_pure_functions():
    """可选计数与保存都走 agentRestrictions.ts，不在组件里另写一套判定。"""
    dialog = _source(DIALOG)
    utils = _source(UTILS)

    assert "isNotRestrictable" in utils, "判定函数只能有一份"
    assert "!isGloballyForbidden(item) && !isNotRestrictable(item)" in utils, (
        "可勾选集合要同时排除全局禁用与不可限定，页签分母才不会虚高"
    )
    assert "strippedIds" in utils, "剥离集合要统一命名，供计数/清洗/payload 共用"
    # 组件不得自行拼装剥离逻辑
    assert "globallyForbiddenIds" not in dialog
    assert "not_restrictable" in dialog or "not_restrictable" in utils


# --------------------------------------------------------------------------- #
# 顶部说明的呈现与折叠
#
# 它每条都要读一遍才能确认"改的是哪个范围"，所以必须醒目（红色警示、铺满整行）；
# 但又不能一直占着屏幕高度——列表本身就要滚动，所以必须可折叠。
# --------------------------------------------------------------------------- #

def test_scope_hint_is_full_width_red_and_collapsible():
    source = _source(DIALOG)

    # 铺满：说明块不能留在标题那一行里跟标题抢宽度，否则说明被压成一小条
    header_marker = "功能限定<span v-if=\"agentLabel\">"
    hint_marker = "作用范围说明"
    assert header_marker in source and hint_marker in source
    header_close = source.index("</h3>")
    assert source.index(hint_marker) > header_close, (
        "说明块必须移出标题所在的头部容器，否则无法铺满整行"
    )

    # 红色警示：与「禁用资源」页的提示同一套语气（不用 indigo 的普通信息色）
    assert "border-red-200 bg-red-50" in source, "说明块要用红色警示底色"
    assert "border-indigo-200 bg-indigo-50" not in source, (
        "旧的信息色写法必须移除，否则红色与蓝紫并存"
    )

    # 可折叠：受控状态 + aria 关联，而不是纯视觉隐藏
    assert "hintCollapsed" in source, "说明块需要折叠状态"
    assert ':aria-expanded="!hintCollapsed"' in source, "折叠要暴露 aria-expanded"
    assert 'aria-controls="agent-restriction-hint"' in source, "折叠要关联内容区 id"
    assert 'v-show="!hintCollapsed"' in source


def test_scope_hint_reopens_expanded_every_time():
    """每次打开弹框都恢复展开：上次折叠后若一直保持，新管理员会完全看不到作用域说明。"""
    source = _source(DIALOG)
    assert "hintCollapsed.value = false" in source, "打开时必须重置为展开"


def test_dialog_can_collapse_and_expand_all_groups_of_current_tab():
    """一个智能体可能绑几十项、十几个分组，逐个点开很费事。"""
    source = _source(DIALOG)

    assert "toggleAllGroupsInActiveTab" in source
    assert "allGroupsCollapsedInActiveTab" in source
    assert "展开全部" in source and "折叠全部" in source

    # 只作用于当前页签：跨页签一起展开会把另一个页签也铺开，找起来更乱
    assert "activeTabGroups" in source, "范围要收敛到当前页签的可见分组"
    assert "visibleGroupsOf(activeTabData)" not in source, (
        "不得在模板里对可能为 undefined 的页签调用 visibleGroupsOf（会白屏）"
    )
    assert "v-if=\"activeTabGroups.length > 1\"" in source, "只有一个分组时按钮没有意义"


def test_toggle_all_groups_writes_to_the_same_collapsed_set():
    """一键与逐个折叠必须共用 collapsedKeys，否则两种方式状态会打架。"""
    source = _source(DIALOG)
    body = source[source.index("const toggleAllGroupsInActiveTab"):]
    body = body[: body.index("</script>")]
    assert "collapsedKeys.value = next" in body, "必须写回同一个折叠集合"
