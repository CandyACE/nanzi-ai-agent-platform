"""用户页「直配 / 角色继承」的接线契约（F1 / F3 / F4 / F7）。

F1 的要害是**读什么、写什么**必须分离：回显与 payload 只看 `direct_permissions`，
`permissions`（并集）只用来算「哪些禁用来自角色」并只读展示。这是防"角色级禁用被
固化成用户级记录"的唯一办法——后端那层剔除只是防御，前端不能依赖它。

F3 的要害是**同一份真实状态**：权限 tab 的显示、拉取、保存三处判定必须同源，且身份一律
取"打开对话框时后端给的角色"，不是可编辑的 `formData.role`。否则管理员改成普通用户再保存，
会把上一个用户的 `permissionData` 整表写出去（越权复制 + 清空黑名单）。
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
USERS = (ROOT / "frontend/src/views/Users.vue").read_text(encoding="utf-8")


def test_users_view_resolves_direct_permissions_through_the_shared_pure_function():
    """页面对 `direct_permissions` / 并集的判断全部委托纯函数，不自己读原始字段。"""
    assert 'from "../utils/permissionLists"' in USERS
    assert "resolveUserPermissionEditState(" in USERS
    # 页面不得自己读原始字段做判定（注释里提到字段名是文档，不算读取）
    assert ".direct_permissions" not in USERS, "回退与差值判定属于纯函数，页面不得自己读该字段"
    assert "response.data.permissions" not in USERS, "页面不得自己取并集"
    assert "const perms = response.data.permissions;" not in USERS, "回显不得再用并集 permissions"
    assert "perms.forbidden_tools || []" not in USERS
    assert "perms.forbidden_skills || []" not in USERS


def test_permission_payload_only_contains_direct_lists():
    """payload 只能由直配缓冲构建：角色来源项没有任何进 payload 的通道。"""
    assert "buildUserPermissionPayload(" in USERS
    assert "forbidden_commands: [...(permissionData.value" not in USERS, "命令不得绕过 payload 构建器"
    assert "...permissionData.value" not in USERS, "不得再整份展开 permissionData 当 payload"


def test_inherited_forbidden_items_are_rendered_read_only():
    """角色来源的禁用项要看得见、带「来自角色」标签与说明，但不能被编辑。"""
    assert "inheritedForbidden.value = state.inherited" in USERS, "角色来源项必须来自纯函数的差值"
    assert "inheritedForbiddenRows" in USERS
    assert "来自角色（只读）" in USERS
    assert "该禁用来自角色，需到角色页调整" in USERS

    read_only_block = USERS.split("<!-- 角色来源的禁用项（只读）")[1].split(
        "<!-- 直配可编辑：禁用工具 / 技能 / 命令 -->"
    )[0]
    assert "inheritedForbiddenRows" in read_only_block
    assert "v-model" not in read_only_block, "只读区不得出现双向绑定"


def test_permission_tab_visibility_fetch_and_save_share_one_state():
    """显示 / 拉取 / 保存三处判定同源，且不再使用可编辑的 formData.role。"""
    assert (
        'const canEditPermissions = computed(\n'
        '  () => showEditDialog.value && permissionSubjectRole.value === "user",\n'
        ");" in USERS
    ), "必须有一个基于真实身份的 canEditPermissions"
    assert "showEditDialog && formData.role === 'user'" not in USERS, "tab 显示不得用可编辑角色"
    assert 'v-show="activeTab === \'permissions\'"' not in USERS, "权限内容区也要同时看真实身份"
    assert 'if (formData.value.role === "user") {' not in USERS, "保存判定不得用可编辑角色"
    assert USERS.count("canEditPermissions") >= 4, "显示 / 拉取 / 保存都必须走同一判定"

    # 真实身份是 user、但这次保存会改成管理员时跳过权限提交：权限对管理员无意义，
    # 且身份切换已按 F3 清空缓冲，硬提交会撞上 F7 守卫、连资料都存不了
    assert "const submitsPermissions =" in USERS
    assert 'canEditPermissions.value && formData.value.role === "user"' in USERS


def test_switching_identity_clears_permission_buffers():
    """身份与打开时的真实角色不一致时立刻清空缓冲，杜绝残留数据被写出去。"""
    assert "resetPermissionBuffers" in USERS
    assert "watch(\n  () => formData.value.role," in USERS, "必须监听角色切换"
    watcher = USERS.split("() => formData.value.role,", 1)[1].split("});", 1)[0]
    assert "resetPermissionBuffers()" in watcher
    # 打开与关闭对话框都要重置：上一个用户的残留不能跨用户存活
    assert USERS.count("resetPermissionBuffers();") >= 3


def test_permission_load_failure_is_surfaced_and_blocks_submission():
    """F7：加载失败必须提示，并且在未成功加载前禁止提交权限。"""
    assert "permissionsLoaded" in USERS
    assert "permissionsLoadError" in USERS
    assert "权限配置加载失败" in USERS, "失败要有明确文案（不能只 console）"
    assert "showToast(permissionsLoadError.value" in USERS, "失败必须弹提示，而不是静默清空"

    save_body = USERS.split("const saveUser = async () => {", 1)[1].split(
        "const toggleStatus = async", 1
    )[0]
    assert "permissionsLoaded.value" in save_body, "保存前必须检查权限是否已成功加载"
    assert save_body.index("permissionsLoaded.value") < save_body.index(
        "buildUserPermissionPayload("
    ), "守卫必须在构建 payload 之前"
    assert "showToast" in save_body


def test_permission_save_happens_before_profile_save():
    """F4：先权限后资料。权限失败时资料不得已提交，否则提示与最终状态矛盾。"""
    save_body = USERS.split("const saveUser = async () => {", 1)[1].split(
        "const toggleStatus = async", 1
    )[0]
    permission_put = save_body.index("/permissions`")
    profile_put = save_body.index("users/${editingUserId.value}`")
    assert permission_put < profile_put, "权限 PUT 必须在用户资料 PUT 之前"
    assert "权限保存失败" in save_body, "权限失败要有独立提示，并与「不提交资料」保持一致"


def test_readable_error_detail_is_used_for_user_saves():
    """F4：422 的 detail 数组必须经纯函数变成人话，不得直接把对象塞进 toast。"""
    assert 'from "../utils/apiErrorDetail"' in USERS
    assert "extractApiErrorDetail(" in USERS
    assert 'error.value = e.response?.data?.detail || e.response?.data?.message || "操作失败";' not in USERS
    assert "showToast(error.value" in USERS
