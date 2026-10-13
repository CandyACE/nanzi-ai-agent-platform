"""角色页的反向契约：角色行本身就是唯一维度，不得被"并集修复"误改成继承模型。

用户页要区分「直配 / 来自角色」是因为 `GET /users/{id}/permissions` 返回并集；
角色页读的是角色行自己的权限，不存在并集问题——所以它不该出现 `direct_permissions`、
「来自角色」只读区这类用户页专属概念。角色级禁用的语义必须原样保留。

这里同时钉住角色页与用户页共享的另外两件事：徽标计数口径（F8）与错误文案可读化（F4）。
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROLES = (ROOT / "frontend/src/views/Roles.vue").read_text(encoding="utf-8")
USERS = (ROOT / "frontend/src/views/Users.vue").read_text(encoding="utf-8")


def test_roles_view_keeps_role_scoped_semantics():
    """角色页不得引入用户页的直配 / 继承概念。"""
    assert "direct_permissions" not in ROLES
    assert "resolveUserPermissionEditState(" not in ROLES
    assert "buildUserPermissionPayload(" not in ROLES
    assert "来自角色（只读）" not in ROLES, "角色页没有「来自角色」这回事，不该渲染只读区"
    assert "inheritedForbidden" not in ROLES
    assert "inheritedForbiddenRows" not in ROLES
    assert "permissionSubjectRole" not in ROLES, "角色页没有「用户身份」这回事"


def test_roles_view_still_reads_and_writes_role_permissions():
    """角色级读写保持原样：并集语义没有被改成"只写直配"。"""
    assert "const perms = response.data.permissions" in ROLES
    assert "`/api/portal/roles/${currentRole.value.id}/permissions`" in ROLES
    assert "forbidden_tools: perms.forbidden_tools || []" in ROLES
    assert "forbidden_skills: perms.forbidden_skills || []" in ROLES


def test_both_views_count_the_badge_through_the_shared_function():
    """F8：两页徽标口径同源；不得再用数组长度当"禁用工具数"。"""
    for name, page in (("Roles.vue", ROLES), ("Users.vue", USERS)):
        assert "/utils/forbiddenResourceBadge" in page, f"{name} 必须复用共享计数"
        assert "countForbiddenResourceBadge(" in page, f"{name} 未接入共享计数函数"
        assert "forbidden_tools?.length" not in page, f"{name} 仍在用数组长度当工具数"
        assert "forbiddenCommandCount" not in page, f"{name} 不该再留一份内联的命令计数"
        assert "forbiddenCommandsText.value.split" not in page, f"{name} 不得自己切分命令文本"
        # 候选目录来自共享缓存（由 ForbiddenToolCatalog 加载），页面不额外发请求
        assert "peekForbiddenCatalog(" in page, f"{name} 徽标计数拿不到候选目录"
        assert "subscribeForbiddenCatalog(" in page, f"{name} 必须订阅目录快照"


def test_roles_view_reports_readable_save_errors():
    """F4：角色页不再只说「保存权限失败」，也不再吞掉 detail。"""
    assert "/utils/apiErrorDetail" in ROLES
    assert "extractApiErrorDetail(" in ROLES
    assert "showToast('保存权限失败', 'error')" not in ROLES
    assert "保存权限失败" in ROLES, "仍然要说明是保存权限失败，只是要带上原因"
