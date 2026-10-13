"""分配权限的两页 tab 行：统一徽标 + 「禁用资源」改名（口径 = 禁用工具数 + 禁用命令数 + 禁用技能数）。

用户页原先没有任何徽标；角色页有，但用 `v-if="type !== 'forbidden_configs'"` 把这一项排除了
（因为 `permissionData` 里没有 `forbidden_configs` 数组，它是 tab 名，内容分别存在
`forbidden_tools` 与 `forbidden_commands`）。本测试锁定两页行为一致。
"""

from pathlib import Path


USERS = Path("frontend/src/views/Users.vue")
ROLES = Path("frontend/src/views/Roles.vue")
COMPONENT = Path("frontend/src/components/system/ForbiddenToolCatalog.vue")
COMMANDS = Path("frontend/src/utils/forbiddenCommands.ts")


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_both_views_rename_the_tab_to_disabled_resources():
    for view in (USERS, ROLES):
        source = _source(view)
        assert "禁用资源" in source, f"{view} 未改用新标题"
        assert "禁用工具与命令" not in source, f"{view} 仍残留旧标题"


def test_both_views_render_a_badge_on_the_same_single_code_path():
    """两页都用同一个计数入口渲染徽标，且徽标样式与角色页既有实现一致。"""
    for view in (USERS, ROLES):
        source = _source(view)
        assert "resourceTabCount(type)" in source, f"{view} 的徽标没有走统一计数"
        assert "rounded-full bg-gray-100 text-gray-600" in source


def test_roles_no_longer_excludes_forbidden_configs_from_the_badge():
    source = _source(ROLES)

    assert "type !== 'forbidden_configs'" not in source, "角色页仍把禁用资源排除在徽标之外"
    assert "type !== \"forbidden_configs\"" not in source


def test_badge_count_for_disabled_resources_covers_tools_commands_and_skills():
    for view in (USERS, ROLES):
        source = _source(view)
        assert "forbiddenCommandCount" in source, f"{view} 的徽标没算禁用命令"
        assert "forbidden_tools" in source
        # 命令数取编辑中的文本，实时反映尚未保存的输入
        assert "forbiddenCommandsText.value" in source

        # 技能是勾选式数组：直接用已勾选个数，不需要像命令那样实时解析文本
        badge = source.split("const resourceTabCount", 1)[1].split(";", 1)[0]
        assert "forbidden_tools" in badge, f"{view} 的徽标没算禁用工具"
        assert "forbiddenCommandCount" in badge, f"{view} 的徽标没算禁用命令"
        assert "forbidden_skills" in badge, f"{view} 的徽标没算禁用技能"
        assert "parseForbiddenCommands" not in badge, "技能数不该走命令的文本解析"


def test_command_parsing_has_a_single_shared_source():
    """保存流程与徽标计数必须共用同一份解析，不能再内联 split 出第二份。"""
    for view in (USERS, ROLES):
        source = _source(view)
        assert "parseForbiddenCommands" in source
        assert 'split(",")' not in source, f"{view} 仍内联解析命令（会有两份解析漂移）"

    assert "export function parseForbiddenCommands" in _source(COMMANDS)


def test_only_the_tab_title_changed():
    """只改 tab 标题：内容区区段标题与历史区文案不得被顺手改掉。"""
    component = _source(COMPONENT)
    for copy in (
        "选择要禁用的工具",
        "自定义 API 与 MCP 扩展工具禁用",
        "其他已禁用项（历史）",
    ):
        assert copy in component, f"内容区文案被改动：{copy}"

    # 「（全局拉黑）」是冗余标注：整个 tab 配的都是全局禁用（顶部说明已写明
    # "该用户完全无法调用该工具"），只给其中一个区段加标注会让人误以为另一块
    # 作用域不同——用户两次追问"这个也是全局拉黑的吧"正是这么来的。
    assert "全局拉黑" not in component

    assert "禁用资源" not in component, "「禁用资源」只应出现在 tab 标题，不应改写内容区"
