"""禁用工具目录：两页共用组件、不再硬编码候选清单。"""

from pathlib import Path


USERS = Path("frontend/src/views/Users.vue")
ROLES = Path("frontend/src/views/Roles.vue")
COMPONENT = Path("frontend/src/components/system/ForbiddenToolCatalog.vue")


def test_users_and_roles_share_the_catalog_component():
    for view in (USERS, ROLES):
        source = view.read_text(encoding="utf-8")
        assert "ForbiddenToolCatalog" in source
        assert "availableToolsToForbid" not in source
        assert "fetchAllSystemTools" not in source
        assert "otherAvailableTools" not in source
        assert "toolSearchQuery" not in source


def test_catalog_component_renders_groups_aliases_and_orphans():
    source = COMPONENT.read_text(encoding="utf-8")

    assert "/api/portal/tools/forbidden-catalog" in source
    assert "同时拦截：" in source
    assert "其他已禁用项（历史）" in source
    # v2 分组重写后单卡片的命名从 group 换成 candidate（"组"一词现在指子组，
    # `group.aliases` 会被读成子组的 aliases 而误导）。语义完全不变：
    # 勾选仍按 aliases 整组写入 / 移除，orphan 处理不变。
    assert "isCandidateSelected" in source
    assert "toggleCandidate" in source
    assert "toggleOrphan" in source
    assert "candidate.aliases" in source


def test_users_page_copy_targets_the_user_not_the_agent():
    source = USERS.read_text(encoding="utf-8")

    assert "配置禁用工具后该用户完全无法调用该工具" in source
    assert "配置禁用工具后该智能体完全无法调用该工具" not in source


def test_catalog_can_collapse_and_expand_all_groups_at_once():
    """一键折叠/展开：候选可达上百条、子组十几个，逐个点开很费事。"""
    source = COMPONENT.read_text(encoding="utf-8")

    assert "toggleAllGroups" in source
    assert "allGroupsCollapsed" in source
    assert "展开全部" in source and "折叠全部" in source

    # 必须覆盖**子组**，不能只折叠三个大组——子组才是列表变长的原因
    body = source[source.index("const collapsibleKeys"):]
    body = body[: body.index("const allGroupsCollapsed")]
    assert "GROUP_BUILTIN_KEY" in body and "GROUP_DYNAMIC_KEY" in body
    assert "visibleBuiltinGroups.value.map((group) => group.key)" in body, "内置子组要算进去"
    assert "visibleDynamicGroups.value.map((group) => group.key)" in body, "动态子组要算进去"
    assert "visibleSkillGroups.value.map((group) => group.key)" in body, "技能子组要算进去"

    # 搜索期间分组强制展开（isExpanded 的只读覆盖），此时按钮没有意义
    assert 'v-if="!isSearching && collapsibleKeys.length > 1"' in source

    # 一键与逐个折叠共用同一个集合
    toggle_body = source[source.index("const toggleAllGroups"):]
    toggle_body = toggle_body[: toggle_body.index("</script>")]
    assert "collapsedKeys.value = next" in toggle_body
