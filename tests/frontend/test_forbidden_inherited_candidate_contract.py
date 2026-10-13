"""禁用资源直配区：已由所属角色禁用的候选必须置灰，不能让人勾了却保存不进去。

背景（ai review 核实项 3）：后端 `update_user_permissions` 对「已由角色派生」的禁用项会
`continue` 丢弃（这是 F1 直配/继承隔离的有意设计，避免把继承项固化成用户直配而无法解绑）。
但前端直配候选区没有相应提示，管理员勾选后界面显示"保存成功"，重新打开勾选却消失了；
更糟的是若之后角色侧解禁，该用户会**直接解禁**，与管理员的预期相反。
"""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
COMPONENT = ROOT / "frontend/src/components/system/ForbiddenToolCatalog.vue"
USERS = ROOT / "frontend/src/views/Users.vue"
PURE = ROOT / "frontend/src/utils/permissionLists.ts"


def _extract_arrow_function_body(source: str, name: str) -> str:
    """粗提取 `export function <name>(...) { ... }` 的函数体（按大括号配平）。"""
    marker = f"export function {name}("
    start = source.index(marker)
    brace = source.index("{", start)
    depth = 0
    for index in range(brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[brace : index + 1]
    raise AssertionError(f"未找到 {name} 的函数体")


def test_pure_function_exists_and_handles_aliases():
    """判定必须覆盖 aliases：后端按提交的 id 逐个比对派生集合，别名命中同样会被丢弃。"""
    source = PURE.read_text(encoding="utf-8")
    assert "export function isInheritedForbiddenCandidate(" in source

    body = _extract_arrow_function_body(source, "isInheritedForbiddenCandidate")
    assert "aliases" in body, "必须把候选的 aliases 一并纳入判定，否则别名组会漏判"
    assert "inherited" in body


def test_component_locks_inherited_candidates():
    source = COMPONENT.read_text(encoding="utf-8")

    assert "inherited" in source, "组件必须接收 inherited 入参"
    assert "isCandidateLocked" in source, "必须有统一的「该候选是否被锁」判定"
    assert "isInheritedForbiddenCandidate(" in source, "判定要复用共享纯函数，不得各写一份"
    # 三处候选项（内置工具 / 自定义 API / 技能）都要置灰。
    # 只数勾选框，不数同一表达式在卡片样式里的出现（那是另一处用途，数量会变）。
    assert source.count(':disabled="disabled || isCandidateLocked(candidate)"') == 3, (
        "三处候选（内置工具、自定义 API 工具、公共技能）的勾选框都要考虑继承锁定"
    )
    assert "已由所属角色禁用" in source, "必须说明为什么点不动"


def test_group_select_never_picks_locked_candidates():
    """全选也不能勾中锁定项：后端会丢弃，勾了只会变成「保存落空」。"""
    source = COMPONENT.read_text(encoding="utf-8")
    body = source[source.index("const toggleSelection =") :]
    body = body[: body.index("\n}") + 2]

    assert "isCandidateLocked" in body, (
        "toggleSelection 必须先剔除锁定项，否则全选仍会勾中被角色禁用的项"
    )


def test_users_view_passes_inherited_lists():
    source = USERS.read_text(encoding="utf-8")

    assert ":inherited=" in source, "用户页必须把继承项传给候选组件"
    assert "inheritedForbidden.forbidden_tools" in source, "工具实例要传继承的工具"
    assert "inheritedForbidden.forbidden_skills" in source, "技能实例要传继承的技能"


def test_roles_view_does_not_pass_inherited():
    """角色页没有"继承"这一层（读的就是角色行本身），传了会误导成整页不可编辑。"""
    roles = (ROOT / "frontend/src/views/Roles.vue").read_text(encoding="utf-8")
    assert ":inherited=" not in roles
