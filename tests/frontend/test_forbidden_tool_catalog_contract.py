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
