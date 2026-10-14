"""「禁用资源」页四页签容器的契约（工具｜MCP｜技能｜命令）。

分页签的动机是三个具体问题，测试就钉这三件事：
1. 改造前工具与技能各有一个搜索框同时显示，用户不知道该在哪个里搜 → 一屏只渲染一类；
2. 命令区（自由关键词输入）要滚动才看得到，且和勾选列表语义不齐 → 独立成页签；
3. 「来自角色（只读）」是跨类别全景，按类别拆进各页签就得逐个翻 → 固定在页签上方。
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CONTAINER = ROOT / "frontend/src/components/system/ForbiddenResourceTabs.vue"
USERS = ROOT / "frontend/src/views/Users.vue"
ROLES = ROOT / "frontend/src/views/Roles.vue"

pytestmark = pytest.mark.no_infrastructure


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_container_has_exactly_four_tabs_in_order():
    source = _src(CONTAINER)
    labels = re.findall(r"label: '([^']+)'", source)
    assert labels == ["工具", "MCP", "技能", "命令"], f"页签顺序与数量都不应对不上：{labels}"


def test_tools_and_mcp_tabs_share_one_selection_list():
    """工具与 MCP 本质是同一份禁用清单（都是 `forbidden_tools`），只是按来源拆开展示。

    两个实例若各绑一份状态，切页签时后一个会把前一个的勾选整体覆盖掉——而保存是
    覆盖式写入，等于静默丢失一半限制。
    """
    source = _src(CONTAINER)
    assert source.count(':model-value="forbiddenTools"') == 2
    assert source.count("tool-scope=\"tools\"") == 1
    assert source.count("tool-scope=\"mcp\"") == 1
    # 只有技能页签绑定另一份清单
    assert source.count(':model-value="forbiddenSkills"') == 1


def test_only_active_tab_is_rendered():
    """一屏只处理一类：否则搜索框会同时出现好几个。"""
    source = _src(CONTAINER)
    for tab in ("tools", "mcp", "skills", "commands"):
        assert f"activeTab === '{tab}'" in source, f"{tab} 页签缺少显示条件"


def test_commands_tab_has_no_denominator():
    """命令是自由输入的关键词，没有候选目录，所以计数只给已禁数量、不给分母。

    给一个假分母（比如 0）会显示成「命令 (3/0)」，看起来像数据坏了。
    """
    source = _src(CONTAINER)
    assert "total: null" in source, "命令页签分母必须为空"
    # 模板里 `total !== null` 才渲染 (n/m)，否则退化成只显示已禁数量
    assert "v-if=\"tab.total !== null\"" in source
    assert "countForbiddenCommands(props.commandsText)" in source, "命令计数走共享解析函数"


def test_inherited_slot_sits_above_the_tabs():
    """跨类别的全景视图固定在页签上方，不随页签切换。"""
    source = _src(CONTAINER)
    assert '<slot name="inherited" />' in source
    assert source.index('<slot name="inherited" />') < source.index('role="tablist"'), (
        "继承区必须在页签之前渲染"
    )


def test_container_counts_from_the_shared_catalog_cache():
    """页签计数只订阅共享缓存，不自己发请求——目录由内部的目录实例统一加载。"""
    source = _src(CONTAINER)
    assert "peekForbiddenCatalog" in source
    assert "subscribeForbiddenCatalog" in source
    assert "loadForbiddenCatalog" not in source, "容器不得自己拉目录，否则一页会请求两次"
    assert source.count("toolCandidatesOf('tools')") >= 1
    assert source.count("toolCandidatesOf('mcp')") >= 1


def test_container_does_not_own_save_logic():
    """三份状态都用 v-model 交回父页面，保存时机由父页面决定（两页保存口径不同）。"""
    source = _src(CONTAINER)
    for prop in ("forbiddenTools", "forbiddenSkills", "commandsText"):
        assert f"update:{prop}" in source, f"{prop} 必须向上抛出变更"
    assert "axios" not in source and "api." not in source, "容器不参与任何提交"


def test_both_views_pass_the_command_subject_for_their_own_wording():
    """命令说明的文案主体两页不同：用户页「该用户」，角色页「该角色下的用户」。"""
    users = _src(USERS)
    roles = _src(ROLES)
    assert 'command-subject="该用户"' in users
    assert 'command-subject="该角色下的用户"' in roles
    # 角色页没有「继承」这一层（读的就是角色行本身）
    assert "inherited-tools" not in roles and "inherited-skills" not in roles


def test_users_view_disables_the_tabs_until_permissions_are_loaded():
    """权限未加载成功时禁止编辑：一次网络抖动会把真实配置整体清掉。"""
    assert ':disabled="!permissionsLoaded"' in _src(USERS)
