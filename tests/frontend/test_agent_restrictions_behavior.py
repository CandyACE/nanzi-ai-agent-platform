"""智能体级资源限制的纯函数行为（用户/角色 × 单个智能体 × 资源）。

背景：平台已有「全局禁用资源」（用户/角色拉黑工具/命令/技能，在所有智能体里生效）。
本次新增一层更细的作用域：**同一个用户在不同智能体里该有不同的资源边界**。
语义仍是「排除」——所以已全局禁用的项在本弹框里**只读置灰、不可勾选**（排除只增不减，
在这里放开全局禁与会与全局语义打架）。

口径（与产品逐条确认）：
  1. 待禁条目按「该智能体实际绑定的条目」列；MCP 只作为分组标题，存的是**具体工具名**；
  2. 不存在命令这一层（命令禁用仍只由全局禁用资源管理）；
  3. 分组可迭代，**不硬编码四组**（MCP 组数量不定）。

这些函数必须只有一份实现（`frontend/src/utils/agentRestrictions.ts`）：用户页与角色页
各写一份必然漂移成两套联邦判定。
"""

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE = "frontend/src/utils/agentRestrictions.ts"
pytestmark = pytest.mark.no_infrastructure

HARNESS = """
(async () => {
const fs = require('fs');
const path = require('path');
const ts = require('./frontend/node_modules/typescript');
const loaded = new Map();
const loadModule = (absolute) => {
  if (loaded.has(absolute)) return loaded.get(absolute).exports;
  const source = fs.readFileSync(absolute, 'utf8');
  const code = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 }
  }).outputText;
  const moduleRef = { exports: {} };
  loaded.set(absolute, moduleRef);
  const localRequire = (id) => {
    if (id.startsWith('.')) {
      const base = path.resolve(path.dirname(absolute), id);
      const hit = [base, base + '.ts', base + '.js'].find(
        (candidate) => fs.existsSync(candidate) && fs.statSync(candidate).isFile(),
      );
      if (hit) return loadModule(hit);
    }
    return require(id);
  };
  new Function('module', 'exports', 'require', code)(moduleRef, moduleRef.exports, localRequire);
  return moduleRef.exports;
};
const api = loadModule(path.resolve(__MODULE__));
const result = await (async () => { __EXPRESSION__ })();
process.stdout.write(JSON.stringify(result));
})().catch(error => { console.error(error); process.exit(1); });
"""


def _run_typescript(expression: str):
    script = HARNESS.replace("__MODULE__", json.dumps(MODULE)).replace("__EXPRESSION__", expression)
    completed = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


# 与后端 GET /api/portal/agents/{id}/restrictable-resources 的形状一致。
# 两个 MCP 组用来钉「组数量不定，不得硬编码四组」。
GROUPS = [
    {
        "key": "builtin_tools",
        "label": "内置工具",
        "items": [
            {"id": "read_file", "label": "读取文件", "forbidden_globally": False},
            {"id": "write_file", "label": "写入/修改文件", "forbidden_globally": True},
        ],
    },
    {
        "key": "mcp:server-a",
        "label": "天气 MCP",
        "items": [{"id": "mcp_a_forecast", "label": "查天气", "forbidden_globally": False}],
    },
    {
        "key": "mcp:server-b",
        "label": "地图 MCP",
        "items": [{"id": "mcp_b_route", "label": "路径规划", "forbidden_globally": False}],
    },
    {
        "key": "public_skills",
        "label": "公共技能",
        "items": [{"id": "skill:report", "label": "报表生成", "forbidden_globally": False}],
    },
    {
        "key": "personal_skills",
        "label": "个人技能",
        "items": [{"id": "skill:mine", "label": "我的技能", "forbidden_globally": False}],
    },
]
GROUPS_JSON = json.dumps(GROUPS, ensure_ascii=False)


def test_groups_are_normalized_and_iterated_not_hardcoded():
    """分组直接来自接口且保序：多一个 MCP server 就多一组，前端不写死四组。"""
    result = _run_typescript(
        f"""
const groups = api.normalizeRestrictableGroups({{ groups: {GROUPS_JSON} }});
const withExtra = api.normalizeRestrictableGroups({{ groups: {GROUPS_JSON}.concat([
  {{ key: 'mcp:server-c', label: '第三个 MCP', items: [{{ id: 'mcp_c_x', label: 'X' }}] }},
]) }});
return {{
  keys: groups.map((group) => group.key),
  labels: groups.map((group) => group.label),
  mcpGroups: groups.filter((group) => group.key.startsWith('mcp:')).length,
  extraGroups: withExtra.length,
  firstItem: groups[0].items[0],
  globallyFlagDefaultsToFalse: groups[4].items[0].forbidden_globally,
}};
"""
    )

    assert result["keys"] == [
        "builtin_tools",
        "mcp:server-a",
        "mcp:server-b",
        "public_skills",
        "personal_skills",
    ], "分组顺序必须与接口一致"
    assert result["labels"] == ["内置工具", "天气 MCP", "地图 MCP", "公共技能", "个人技能"]
    assert result["mcpGroups"] == 2, "MCP 组数量由接口决定"
    assert result["extraGroups"] == 5 + 1, "多一个 MCP server 必须多渲染一组"
    assert result["firstItem"] == {
        "id": "read_file",
        "label": "读取文件",
        "forbidden_globally": False,
    }
    assert result["globallyFlagDefaultsToFalse"] is False, "接口没给 forbidden_globally 时按未全局禁用"


def test_bad_shapes_are_tolerated():
    """坏数据（null / 非数组 / 空 id / 非对象）按空处理，不得抛错也不得造出幽灵条目。"""
    result = _run_typescript(
        """
const cases = [null, [], 'nope', 0, { groups: null }];
return {
  empties: cases.map((value) => api.normalizeRestrictableGroups(value).length),
  withoutGroupsKey: api.normalizeRestrictableGroups([{ key: 'k', label: 'L', items: [{ id: 'a' }] }]).length,
  fallbackKeyAndLabel: api.normalizeRestrictableGroups({ groups: [{ items: [{ id: 'a' }] }] }),
  itemsNotArray: api.normalizeRestrictableGroups({ groups: [{ key: 'k', label: 'L', items: 'nope' }] }).length,
  blankIdSkipped: api.normalizeRestrictableGroups({ groups: [{ key: 'k', label: 'L', items: [{ id: '  ' }, null, { id: 'ok' }] }] }),
  labelFallsBackToId: api.normalizeRestrictableGroups({ groups: [{ key: 'k', label: 'L', items: [{ id: 'ok' }] }] })[0].items[0].label,
  dirtyFlagCoerced: api.normalizeRestrictableGroups({ groups: [{ key: 'k', label: 'L', items: [{ id: 'a', forbidden_globally: 1 }, { id: 'b', forbidden_globally: 0 }] }] })[0].items.map((item) => item.forbidden_globally),
};
"""
    )

    assert result["empties"] == [0, 0, 0, 0, 0]
    assert result["withoutGroupsKey"] == 0, "整体响应（而非裸数组）才是接口契约，裸数组不猜"
    assert result["fallbackKeyAndLabel"] == [
        {"key": "__restrictable_group_0__", "label": "__restrictable_group_0__", "items": [{"id": "a", "label": "a", "forbidden_globally": False}]}
    ], "缺 key 的分组要有稳定兜底键（与 forbiddenToolGroups 的兜底同思路），不能丢条目不渲染"
    assert result["itemsNotArray"] == 0, "没有条目的分组不占位"
    assert result["blankIdSkipped"] == [{"key": "k", "label": "L", "items": [{"id": "ok", "label": "ok", "forbidden_globally": False}]}]
    assert result["labelFallsBackToId"] == "ok"
    assert result["dirtyFlagCoerced"] == [True, False]


def test_globally_forbidden_items_are_readonly_and_never_selectable():
    """已全局禁用的项：不可勾选（勾选不写进选择集），也不参与「全选」的完成判定。"""
    result = _run_typescript(
        f"""
const groups = api.normalizeRestrictableGroups({{ groups: {GROUPS_JSON} }});
const builtin = groups[0];
const onlyForbidden = api.normalizeRestrictableGroups({{ groups: [
  {{ key: 'public_skills', label: '公共技能', items: [{{ id: 'skill:x', label: 'X', forbidden_globally: true }}] }},
] }})[0];
return {{
  checked: api.applyGroupRestrictionSelection([], builtin.items, true),
  unchecked: api.applyGroupRestrictionSelection(['read_file', 'write_file'], builtin.items, false),
  stateEmpty: api.groupSelectionState([], builtin.items),
  stateAfterSelect: api.groupSelectionState(['read_file'], builtin.items),
  stateDirty: api.groupSelectionState(['write_file'], builtin.items),
  onlyForbiddenAll: api.groupSelectionState([], onlyForbidden.items),
  sanitized: api.sanitizeAgentRestrictionLists(
    {{ forbidden_tools: ['read_file', 'write_file'], forbidden_skills: [] }},
    groups,
  ),
}};
"""
    )

    assert result["checked"] == ["read_file"], "全局禁用项不得被勾选写入（排除只增不减）"
    assert result["unchecked"] == [], "取消全选仍可移除本组已有的（含全局项）记录"
    assert result["stateEmpty"] == {"selected": 0, "selectable": 1, "allSelected": False}
    assert result["stateAfterSelect"] == {"selected": 1, "selectable": 1, "allSelected": True}
    assert result["stateDirty"] == {
        "selected": 0,
        "selectable": 1,
        "allSelected": False,
    }, "只有全局禁用项被选中时不得显示成「已全选」"
    assert result["onlyForbiddenAll"] == {
        "selected": 0,
        "selectable": 0,
        "allSelected": False,
    }, "一组全是全局禁用项时不得自动全选（否则会写进 payload）"
    assert result["sanitized"]["forbidden_tools"] == ["read_file"], "回显要剔除全局禁用项，与本弹框口径一致"


def test_counts_are_deduped_and_global_items_ignored_when_catalog_known():
    """计数（弹框「已选 N 项」与卡片角标）去重；有目录时全局禁用项不计入。"""
    result = _run_typescript(
        f"""
const groups = api.normalizeRestrictableGroups({{ groups: {GROUPS_JSON} }});
return {{
  dedup: api.countRestrictionEntries(['read_file', 'read_file', 'legacy_x'], groups),
  globallyForbiddenIgnored: api.countRestrictionEntries(['write_file'], groups),
  unknownCatalog: api.countRestrictionEntries(['write_file'], []),
  badgeFromLists: api.countAgentRestrictionBadge({{
    forbidden_tools: ['write_file', 'read_file', 'read_file'],
    forbidden_skills: ['skill:report', 'skill:report'],
  }}),
  badgeWithCatalog: api.countAgentRestrictionBadge(
    {{ forbidden_tools: ['write_file', 'read_file'], forbidden_skills: [] }},
    groups,
  ),
  badgeBadShape: api.countAgentRestrictionBadge({{ forbidden_tools: null, forbidden_skills: 'nope' }}),
}};
"""
    )

    assert result["dedup"] == 2, "重复项不膨胀；不在目录里的历史项各算 1"
    assert result["globallyForbiddenIgnored"] == 0, "目录已知时全局禁用项不算本层限制"
    assert result["unknownCatalog"] == 1, "目录未知时退化为去重计数，宁可短暂等于旧口径也不能少算"
    assert result["badgeFromLists"] == 3
    assert result["badgeWithCatalog"] == 1
    assert result["badgeBadShape"] == 0


def test_payload_only_contains_this_agents_restriction_lists():
    """payload 只含该智能体的两项限制：覆盖式写入，空数组 = 清空，绝不带全局字段/命令。"""
    result = _run_typescript(
        f"""
const groups = api.normalizeRestrictableGroups({{ groups: {GROUPS_JSON} }});
const payload = api.buildAgentRestrictionPayload({{
  forbidden_tools: ['read_file', 'read_file', '', 'write_file', 'legacy_x'],
  forbidden_skills: ['skill:report', 'skill:report', '  '],
  forbidden_commands: ['rm'],
  agents: ['agent-1'],
}}, groups);
const empty = api.buildAgentRestrictionPayload({{}}, groups);
return {{
  payload,
  keys: Object.keys(payload).sort(),
  empty,
}};
"""
    )

    assert result["keys"] == ["forbidden_skills", "forbidden_tools"], "payload 结构必须与后端一致"
    assert result["payload"]["forbidden_tools"] == [
        "read_file",
        "legacy_x",
    ], "去重去空、剔除全局禁用项；不在目录里的历史项保留（由用户显式清理，不静默删除）"
    assert result["payload"]["forbidden_skills"] == ["skill:report"]
    assert "forbidden_commands" not in result["payload"], "命令禁用不属于本层作用域"
    assert "agents" not in result["payload"]
    assert result["empty"] == {"forbidden_tools": [], "forbidden_skills": []}, "空数组 = 清空"


def test_unbound_detection_and_search():
    """解绑/改名的历史项要可识别、可一键清理；搜索按分组与条目匹配。"""
    result = _run_typescript(
        f"""
const groups = api.normalizeRestrictableGroups({{ groups: {GROUPS_JSON} }});
return {{
  unbound: api.findUnboundRestrictionIds(['read_file', 'legacy_x', 'mcp_a_forecast'], groups),
  noneUnbound: api.findUnboundRestrictionIds(['read_file'], groups),
  byGroupLabel: api.filterRestrictableGroups(groups, '天气').map((group) => group.key),
  byGroupKey: api.filterRestrictableGroups(groups, 'mcp:server-b').map((group) => group.key),
  byItemId: api.filterRestrictableGroups(groups, 'skill:report').map((group) => group.key),
  byItemLabel: api.filterRestrictableGroups(groups, '路径').map((group) => group.key),
  caseInsensitive: api.filterRestrictableGroups(groups, 'MCP:SERVER-A').map((group) => group.key),
  noHit: api.filterRestrictableGroups(groups, 'zzz').length,
  emptyQuery: api.filterRestrictableGroups(groups, '   ').length,
}};
"""
    )

    assert result["unbound"] == ["legacy_x"]
    assert result["noneUnbound"] == []
    assert result["byGroupLabel"] == ["mcp:server-a"]
    assert result["byGroupKey"] == ["mcp:server-b"]
    assert result["byItemId"] == ["public_skills"]
    assert result["byItemLabel"] == ["mcp:server-b"]
    assert result["caseInsensitive"] == ["mcp:server-a"]
    assert result["noHit"] == 0
    assert result["emptyQuery"] == 5


def test_group_kind_mapping_is_shared():
    """工具 / 技能归属判定只有一份：技能组写 forbidden_skills，工具组（含 MCP）写 forbidden_tools。

    接口的 groups 不带类型字段，只能按分组键判定；判定散在组件里就会在「后端加一个技能来源」
    时漏掉一类。名字里恰好带 skills 的 MCP server 也不能被误判成技能。
    """
    result = _run_typescript(
        f"""
const groups = api.normalizeRestrictableGroups({{ groups: {GROUPS_JSON} }});
const mapped = {{}};
groups.forEach((group) => {{ mapped[group.key] = api.resourceKindOfGroup(group); }});
mapped['mcp:skills-market'] = api.resourceKindOfGroup({{ key: 'mcp:skills-market', label: '', items: [] }});
mapped['裸 skills'] = api.resourceKindOfGroup({{ key: 'skills', label: '', items: [] }});
mapped['null group'] = api.resourceKindOfGroup(null);
return mapped;
"""
    )

    assert result == {
        "builtin_tools": "tools",
        "mcp:server-a": "tools",
        "mcp:server-b": "tools",
        "public_skills": "skills",
        "personal_skills": "skills",
        "mcp:skills-market": "tools",
        "裸 skills": "skills",
        "null group": "tools",
    }


def test_restriction_endpoints_live_in_one_place():
    """接口路径只有一处来源：两页与弹框都调这里，不得各自拼字符串。

    三点契约（与后端 management.py 实际实现对齐）：
      1. 智能体级限制全部挂在 `/api/portal/management` 下；
      2. 候选清单必须带视角参数（user_id / role_id）——`forbidden_globally` 是相对
         这个用户 / 角色算的，不带就没法置灰全局禁用项；
      3. 候选清单的缓存键必须带视角，否则会串号。
    """
    result = _run_typescript(
        """
return {
  catalogUser: api.agentRestrictableResourcesPath('user', 7, 'agent-1'),
  catalogRole: api.agentRestrictableResourcesPath('role', 3, 'agent-1'),
  catalogTrimmed: api.agentRestrictableResourcesPath('user', 7, '  agent-1  '),
  user: api.agentRestrictionPath('user', 7, 'agent-1'),
  role: api.agentRestrictionPath('role', 3, 'agent-1'),
  userKey: api.agentRestrictionCacheKey('user', 7, 'agent-1'),
  roleKey: api.agentRestrictionCacheKey('role', 7, 'agent-1'),
  catalogKeyUser: api.agentRestrictableCatalogCacheKey('user', 7, 'agent-1'),
  catalogKeyRole: api.agentRestrictableCatalogCacheKey('role', 7, 'agent-1'),
};
"""
    )

    assert result["catalogUser"] == (
        "/api/portal/management/agents/agent-1/restrictable-resources?user_id=7"
    ), "候选清单必须以用户视角取数，否则全局禁用项不会置灰"
    assert result["catalogRole"] == (
        "/api/portal/management/agents/agent-1/restrictable-resources?role_id=3"
    ), "角色视角用 role_id"
    assert result["catalogTrimmed"] == (
        "/api/portal/management/agents/agent-1/restrictable-resources?user_id=7"
    )
    assert (
        result["user"] == "/api/portal/management/users/7/agent-restrictions/agent-1"
    ), "用户侧与 /users/{id}/permissions 同族前缀"
    assert (
        result["role"] == "/api/portal/management/roles/3/agent-restrictions/agent-1"
    ), "角色侧与用户侧同族，都在 management 下"
    assert result["userKey"] != result["roleKey"], "同一 id 的用户与角色必须落在不同的缓存槽"
    assert result["catalogKeyUser"] != result["catalogKeyRole"], (
        "候选清单缓存键必须带视角，否则会把上一个用户的置灰结果带给下一个"
    )
    assert result["catalogKeyUser"] != result["userKey"], (
        "候选清单与限制列表是两份缓存，键必须可区分"
    )


def test_restriction_snapshot_normalization():
    """GET 回显的归一化：坏形状按空数组，不得把 null 当字符串遍历。"""
    result = _run_typescript(
        """
return {
  normal: api.normalizeAgentRestriction({ forbidden_tools: ['a', 'a', ' '], forbidden_skills: ['s'] }),
  nulls: api.normalizeAgentRestriction(null),
  strings: api.normalizeAgentRestriction({ forbidden_tools: 'nope', forbidden_skills: 5 }),
  missing: api.normalizeAgentRestriction({}),
};
"""
    )

    assert result["normal"] == {"forbidden_tools": ["a"], "forbidden_skills": ["s"]}
    assert result["nulls"] == {"forbidden_tools": [], "forbidden_skills": []}
    assert result["strings"] == {"forbidden_tools": [], "forbidden_skills": []}
    assert result["missing"] == {"forbidden_tools": [], "forbidden_skills": []}


# ---------------------------------------------------------------------------
# 页签归类：弹框按「工具 | MCP | SKILLS」分栏，与智能体平台的资源选择一致
#
# 三个页签**固定存在**：智能体绑什么才有什么，某页签为空是正常状态；若按接口返回动态
# 生成页签，"这个智能体为什么没有 SKILLS"就变成无从判断的疑问。
# ---------------------------------------------------------------------------


def test_tabs_are_always_three_even_when_the_agent_binds_nothing():
    result = _run_typescript("""
const tabs = api.groupRestrictionTabs([]);
return { keys: tabs.map((tab) => tab.key), labels: tabs.map((tab) => tab.label),
         groupCounts: tabs.map((tab) => tab.groups.length) };
""")

    assert result["keys"] == ["tools", "mcp", "skills"], "页签固定三个，不随接口返回增减"
    assert result["labels"] == ["工具", "MCP", "SKILLS"], "标签与智能体平台的资源分类一致"
    assert result["groupCounts"] == [0, 0, 0], "空智能体三个页签都为空而不是不留页签"


def test_tabs_group_api_groups_by_resource_kind():
    result = _run_typescript(
        f"""
const tabs = api.groupRestrictionTabs({GROUPS_JSON});
const byKey = {{}};
tabs.forEach((tab) => {{ byKey[tab.key] = tab.groups.map((group) => group.key); }});
const mcpTab = tabs.find((tab) => tab.key === 'mcp');
return {{
  byKey,
  kinds: {{
    personal: api.resourceTabOfGroup({{ key: 'personal_skills' }}),
    team: api.resourceTabOfGroup({{ key: 'team_skills' }}),
    mcp: api.resourceTabOfGroup({{ key: 'mcp:any' }}),
    builtin: api.resourceTabOfGroup({{ key: 'builtin_tools' }}),
    empty: api.resourceTabOfGroup(null),
  }},
  mcpState: api.tabSelectionState(mcpTab, ['mcp_a_forecast']),
  hints: ['tools', 'mcp', 'skills'].map((key) => api.tabEmptyHint(key)),
}};
"""
    )

    assert result["byKey"]["tools"] == ["builtin_tools"], "内置工具归工具页签"
    assert result["byKey"]["mcp"] == ["mcp:server-a", "mcp:server-b"], (
        "每个 MCP server 一个分组，不得合并成一个"
    )
    assert result["byKey"]["skills"] == ["public_skills", "personal_skills"], (
        "公共技能与个人技能同属 SKILLS 页签"
    )
    # 归类收在一处：后端将来新增技能来源只要沿用 _skills 后缀就会落到 SKILLS 页签
    assert result["kinds"] == {
        "personal": "skills",
        "team": "skills",
        "mcp": "mcp",
        "builtin": "tools",
        "empty": "tools",
    }, "归类必须只有一处实现，且容忍键缺失"
    # 页签计数：分母只算可勾选项（全局禁用的项不能勾，不该进分母）
    assert result["mcpState"] == {"selected": 1, "selectable": 2, "allSelected": False}
    for hint in result["hints"]:
        assert "未绑定" in hint, "空页签必须说明原因，而不是留白"


def test_count_restriction_entries_only_accepts_arrays():
    """固化一个易踩的坑：`countRestrictionEntries` 收的是**数组**，传对象恒为 0。

    弹框底部曾这样调用：`countRestrictionEntries({forbidden_tools, forbidden_skills}, groups)`
    ——`normalizeSelectedIds` 对非数组返回 []，于是"已选 N 项"永远显示 0，
    而卡片角标是对的，两个数字当场互相矛盾。
    """
    result = _run_typescript(
        f"""
const lists = {{ forbidden_tools: ['read_file'], forbidden_skills: ['skill:report'] }};
const groups = api.normalizeRestrictableGroups({{ groups: {GROUPS_JSON} }});
return {{
  asObject: api.countRestrictionEntries(lists, groups),
  asArray: api.countRestrictionEntries(['read_file', 'skill:report'], groups),
  viaBadge: api.countAgentRestrictionBadge(lists, groups),
}};
"""
    )

    assert result["asObject"] == 0, "传对象必然得到 0——这正是当时的 bug"
    assert result["asArray"] == 2
    assert result["viaBadge"] == 2, "角标口径才是正确的那个"


def test_users_view_resets_agent_restriction_cache_with_the_subject():
    """用户页必须随主体切换复位智能体级计数与弹框目标。

    获取逻辑对**已有键**会跳过请求（同一次打开里同一智能体只请求一次），所以残留
    不是"多请求一次"的问题：用户 A 的角标会原样挂在用户 B 的卡片上。
    用户 A → B 可能都是普通用户，`resetPermissionBuffers` 的身份 watch 不会触发，
    因此"复位缓冲"和"打开编辑"两处都要清。
    """
    source = (ROOT / "frontend/src/views/Users.vue").read_text(encoding="utf-8")

    reset_body = source[source.index("const resetPermissionBuffers = ()") :]
    reset_body = reset_body[: reset_body.index("\n};") + 3]
    assert "agentRestrictionCounts.value = {}" in reset_body, (
        "复位权限缓冲时必须一并清掉智能体级计数（关闭弹框走的就是这条路径）"
    )
    assert "agentRestrictionTarget.value = null" in reset_body

    edit_body = source[source.index("const editUser = async (user: any) => {") :]
    edit_body = edit_body[: edit_body.index("\n};") + 3]
    assert "agentRestrictionCounts.value = {}" in edit_body, (
        "打开另一个用户时必须复位：同为普通用户时身份 watch 不触发"
    )

    roles = (ROOT / "frontend/src/views/Roles.vue").read_text(encoding="utf-8")
    assert roles.count("agentRestrictionCounts.value = {}") >= 2, (
        "角色页在打开与关闭两处都复位，这是既有正确实现（用户页对齐它）"
    )


def test_regroup_tools_splits_the_two_api_buckets_by_capability():
    """接口的「内置工具 / 自定义 API 工具」两桶 → 能力域分组，与智能体页一致。"""
    result = _run_typescript(
        """
const groups = api.normalizeRestrictableGroups({ groups: [
  { key: 'builtin_tools', label: '内置工具', items: [
    { id: 'read_file', label: 'read_file' },
    { id: 'exec_command', label: 'exec_command' },
    { id: 'browser_click', label: 'browser_click' },
  ] },
  { key: 'api_tools', label: '自定义 API 工具', items: [
    { id: 'crm_sync', label: 'crm_sync', group_name: '客户域' },
    { id: 'plain_thing', label: 'plain_thing' },
  ] },
  { key: 'mcp:server-a', label: '天气', items: [{ id: 'forecast', label: 'forecast' }] },
]});
const regrouped = api.regroupToolGroups(
  groups.filter((group) => group.key === 'builtin_tools' || group.key === 'api_tools'),
);
return {
  regrouped: regrouped.map((group) => ({
    label: group.label,
    ids: group.items.map((item) => item.id),
  })),
  mcpUntouched: api.regroupToolGroups(
    groups.filter((group) => group.key.startsWith('mcp:')),
  ).map((group) => group.key),
};
"""
    )

    assert result["regrouped"] == [
        {"label": "浏览器自动化", "ids": ["browser_click"]},
        {"label": "系统自治工具", "ids": ["read_file", "exec_command"]},
        {"label": "客户域", "ids": ["crm_sync"]},
        {"label": "其他扩展工具", "ids": ["plain_thing"]},
    ], "能力域按固定顺序，业务分组其次，兜底最后；与智能体页完全同构"


def test_regrouped_tool_groups_still_count_as_tools():
    """新组键不能被当成技能：否则勾选会写进 forbidden_skills。

    `resourceKindOfGroup` 只认 `skills` / `*_skills` 后缀，这里把该前提钉住。
    """
    result = _run_typescript(
        """
const keys = ['tools:capability:system', 'tools:business:客户域', 'tools:__other__'];
return keys.map((key) => api.resourceKindOfGroup({ key, label: key, items: [] }));
"""
    )

    assert result == ["tools", "tools", "tools"], "新组键必须仍归工具列"


def test_descriptions_and_source_version_survive_normalization():
    """描述与来源版本都必须透传：前者决定副标题显示什么，后者解释数量差异。"""
    result = _run_typescript(
        """
const catalog = api.normalizeAgentRestrictableCatalog({
  agent_id: 'a1',
  source_version: { id: 'v3', version_number: 3, status: 'PUBLISHED', is_published: true },
  groups: [
    { key: 'builtin_tools', label: '内置工具', items: [
      { id: 'read_file', label: 'read_file', description: '按行读取文件内容' },
      { id: 'no_desc', label: 'no_desc', description: '   ' },
      { id: 'missing', label: 'missing' },
    ] },
  ],
});
const group = catalog.groups[0];
return {
  withDescription: group.items[0].description,
  blankDropped: 'description' in group.items[1],
  missingDropped: 'description' in group.items[2],
  sourceVersion: catalog.sourceVersion,
  groupsKept: catalog.groups.length,
};
"""
    )

    assert result["withDescription"] == "按行读取文件内容"
    assert result["blankDropped"] is False, "空白描述不要留下空串，前端会显示成空白行"
    assert result["missingDropped"] is False
    assert result["groupsKept"] == 1, "目录归一化不能丢掉分组"
    assert result["sourceVersion"] == {
        "id": "v3",
        "version_number": 3,
        "status": "PUBLISHED",
        "is_published": True,
    }


def test_source_version_tolerates_dirty_and_missing_payloads():
    """来源版本是展示信息，坏数据必须降级为 null，绝不能挡住弹框。"""
    result = _run_typescript(
        """
const cases = [
  undefined,
  null,
  'nope',
  {},
  { source_version: null },
  { source_version: {} },
  { source_version: { id: '  ' } },
];
return {
  allNull: cases.map((value) => api.readSourceVersion(value)),
  stringNumber: api.readSourceVersion({
    source_version: { id: 'v9', version_number: '9', status: 'DRAFT', is_published: false },
  }),
  bogusNumber: api.readSourceVersion({
    source_version: { id: 'v9', version_number: 'abc', status: 'DRAFT' },
  }),
  missingPublishedFlag: api.readSourceVersion({ source_version: { id: 'v9' } }),
};
"""
    )

    assert result["allNull"] == [None] * 7, "没有可用 id 时一律 null"
    assert result["stringNumber"]["version_number"] == 9, "字符串版本号要能解析"
    assert result["bogusNumber"]["version_number"] is None, "解析不出来就是 null，不要出现 NaN"
    assert result["missingPublishedFlag"]["is_published"] is False, "缺省按未发布处理"


# ---------------------------------------------------------------------------
# 「不可限定」项（个人技能）：置灰只读，且永不进入本层记录
#
# 后端对个人技能打 not_restrictable 标记，因为权限侧三处过滤全部排除个人技能
# （与公共技能可能同名，只按 id 判定会连坐用户自建的那一份）。界面上它必须
# 既不参与勾选计数，也不能被保存——否则就是"勾了能存、运行时不读"的空转。
# ---------------------------------------------------------------------------

GROUPS_WITH_PERSONAL_JSON = json.dumps(
    [
        {
            "key": "public_skills",
            "label": "公共技能",
            "items": [
                {"id": "pdf", "label": "PDF 处理", "forbidden_globally": False},
                {"id": "legacy_report", "label": "报表", "forbidden_globally": True},
            ],
        },
        {
            "key": "personal_skills",
            "label": "个人技能",
            "items": [
                {
                    "id": "my_skill",
                    "label": "我的技能",
                    "forbidden_globally": False,
                    "not_restrictable": True,
                    "not_restrictable_reason": "个人技能不支持限定：权限侧只对公共技能生效",
                },
            ],
        },
    ]
)


def test_not_restrictable_items_are_not_selectable():
    """可勾选集合排除不可限定项：页签与分组分母都由它推导。"""
    result = _run_typescript(
        f"""
const groups = api.normalizeRestrictableGroups({{ groups: {GROUPS_WITH_PERSONAL_JSON} }});
const personal = groups.find((group) => group.key === 'personal_skills');
return {{
  personalSelectable: api.selectableItems(personal.items).length,
  personalTotal: personal.items.length,
  personalState: api.groupSelectionState(['my_skill'], personal.items),
  flagPassedThrough: personal.items[0].not_restrictable === true,
  reason: personal.items[0].not_restrictable_reason,
}};
"""
    )
    assert result["personalSelectable"] == 0, "个人技能不可勾选，否则仍是空转"
    assert result["personalTotal"] == 1, "但要保留在列表里（管理员需要看到）"
    assert result["personalState"]["selectable"] == 0
    assert result["personalState"]["selected"] == 0, "已存的历史记录也不该计入已选"
    assert result["flagPassedThrough"] is True, "归一化必须透传标记"
    assert "公共技能" in result["reason"], "原因文案要透传到界面"


def test_not_restrictable_items_are_stripped_from_payload_and_count():
    """保存与计数都要剥离：不能出现「角标算进去了但保存不提交」的口径漂移。"""
    result = _run_typescript(
        f"""
const groups = api.normalizeRestrictableGroups({{ groups: {GROUPS_WITH_PERSONAL_JSON} }});
const selected = ['pdf', 'my_skill', 'legacy_report'];
return {{
  payload: api.buildAgentRestrictionPayload({{ forbidden_skills: selected }}, groups),
  sanitized: api.sanitizeAgentRestrictionLists({{ forbidden_skills: selected }}, groups),
  counted: api.countRestrictionEntries(selected, groups),
  badge: api.countAgentRestrictionBadge({{ forbidden_skills: selected }}, groups),
}};
"""
    )
    # pdf 保留；my_skill（不可限定）与 legacy_report（全局禁用）都要剥离
    assert result["payload"]["forbidden_skills"] == ["pdf"]
    assert result["sanitized"]["forbidden_skills"] == ["pdf"]
    assert result["counted"] == 1
    assert result["badge"] == 1


def test_personal_skill_marked_when_also_globally_forbidden():
    """个人技能与同名公共技能可能同时「被全局禁用 + 不可限定」，两个标记都要透传。"""
    result = _run_typescript(
        """
const groups = api.normalizeRestrictableGroups({ groups: [
  { key: 'personal_skills', label: '个人技能', items: [
    { id: 'same_name', label: '同名技能', forbidden_globally: true, not_restrictable: true,
      not_restrictable_reason: '个人技能不支持限定：权限侧只对公共技能生效' },
  ] },
] });
const item = groups[0].items[0];
return { globally: item.forbidden_globally, notRestrictable: item.not_restrictable };
"""
    )
    assert result["globally"] is True
    assert result["notRestrictable"] is True
