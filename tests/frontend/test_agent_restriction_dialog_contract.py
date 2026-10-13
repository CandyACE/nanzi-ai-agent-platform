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
    assert ':disabled="item.forbidden_globally"' in source, "全局禁用项必须置灰不可勾选"
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
