"""禁用工具分组的纯函数行为（spec §4 的第 6～9 项）。

这些函数是组件唯一的聚合/计数/全选/过滤来源，所以直接在 node harness 里
跑真实 TypeScript 实现，不挂载组件——组件只管渲染与折叠状态。
"""

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE = "frontend/src/utils/forbiddenToolGroups.ts"
pytestmark = pytest.mark.no_infrastructure


def _run_typescript(expression: str):
    script = f"""
(async () => {{
const fs = require('fs');
const ts = require('./frontend/node_modules/typescript');
const source = fs.readFileSync({json.dumps(MODULE)}, 'utf8');
const code = ts.transpileModule(source, {{
  compilerOptions: {{ module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 }}
}}).outputText;
const moduleRef = {{ exports: {{}} }};
new Function('module', 'exports', 'require', code)(moduleRef, moduleRef.exports, require);
const api = moduleRef.exports;
const result = await (async () => {{ {expression} }})();
process.stdout.write(JSON.stringify(result));
}})().catch(error => {{ console.error(error); process.exit(1); }});
"""
    completed = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


# 顺序即后端返回顺序：两个 builtin 组相邻、mcp/api 在后——用来验证"聚合保序"。
CANDIDATES = [
    {
        "id": "exec_command",
        "label": "执行终端命令",
        "description": "在沙箱中执行 Bash/shell 命令行",
        "category": "sandbox",
        "aliases": ["exec_command"],
        "group_key": "builtin:sandbox",
        "group": "沙箱命令",
    },
    {
        "id": "write_file",
        "label": "写入/修改文件",
        "description": "写入或修改文件内容",
        "category": "file",
        "aliases": ["write_file", "edit_file", "apply_patch"],
        "group_key": "builtin:file",
        "group": "文件操作",
    },
    {
        "id": "read_file",
        "label": "读取文件",
        "description": "读取文件内容",
        "category": "file",
        "aliases": ["read_file"],
        "group_key": "builtin:file",
        "group": "文件操作",
    },
    {
        "id": "jira_search",
        "label": "Jira 搜索",
        "description": "使用 JQL 语法查询 Jira 历史工单",
        "category": "mcp",
        "aliases": ["jira_search"],
        "group_key": "mcp:jira",
        "group": "MCP · jira",
    },
    {
        "id": "send_email",
        "label": "发送邮件",
        "description": "向指定收件人发送邮件",
        "category": "api",
        "aliases": ["send_email"],
        "group_key": "api:履约罚款",
        "group": "自定义 API · 履约罚款",
    },
]


def test_group_candidates_aggregates_in_first_seen_order():
    """按 group_key 聚合、子组与组内候选都保序、不产生空组；缺 group_key 时兜底不丢候选。"""
    result = _run_typescript(
        f"""
const candidates = {json.dumps(CANDIDATES)};
const groups = api.groupCandidates(candidates);
const legacy = api.groupCandidates([
  {{ id: 'legacy_tool', label: 'legacy_tool', description: '', category: 'builtin', aliases: ['legacy_tool'] }},
]);
return {{
  keys: groups.map((group) => group.key),
  labels: groups.map((group) => group.label),
  ids: groups.map((group) => group.candidates.map((candidate) => candidate.id)),
  emptyInput: api.groupCandidates([]),
  legacyKeys: legacy.map((group) => group.key),
  legacyIds: legacy.map((group) => group.candidates.map((candidate) => candidate.id)),
}};
"""
    )
    assert result["keys"] == [
        "builtin:sandbox",
        "builtin:file",
        "mcp:jira",
        "api:履约罚款",
    ]
    assert result["labels"] == ["沙箱命令", "文件操作", "MCP · jira", "自定义 API · 履约罚款"]
    # 同组候选落在一组，且组内保持后端返回顺序
    assert result["ids"][1] == ["write_file", "read_file"]
    assert result["emptyInput"] == []
    assert all(group_ids for group_ids in result["ids"]), "不得产生空组"
    assert result["legacyKeys"] == ["__ungrouped__"], "缺 group_key 时归入兜底组而不是丢候选"
    assert result["legacyIds"] == [["legacy_tool"]]


def test_group_selected_count_counts_candidates_not_aliases():
    """计数按 aliases 命中算：勾 write_file 只算 1 个候选，即使它带 3 个别名。"""
    result = _run_typescript(
        f"""
const groups = api.groupCandidates({json.dumps(CANDIDATES)});
const fileGroup = groups.find((group) => group.key === 'builtin:file');
return {{
  oneAlias: api.groupSelectedCount(fileGroup, new Set(['edit_file'])),
  wholeGroup: api.groupSelectedCount(fileGroup, new Set(['write_file', 'edit_file', 'apply_patch', 'read_file'])),
  outsideGroup: api.groupSelectedCount(fileGroup, new Set(['exec_command'])),
  arrayForm: api.groupSelectedCount(fileGroup, ['read_file']),
}};
"""
    )
    assert result["oneAlias"] == 1, "一个候选命中多个别名也只算 1"
    assert result["wholeGroup"] == 2, "组内 2 个候选全选中"
    assert result["outsideGroup"] == 0
    assert result["arrayForm"] == 1, "也应接受数组形式的选中集合"


def test_apply_group_selection_union_diff_and_immutability():
    """勾选=并集、取消=差集；保序去重、不修改入参、不触碰组外项（如 orphan）。"""
    result = _run_typescript(
        f"""
const candidates = {json.dumps(CANDIDATES)};
const fileCandidates = candidates.filter((candidate) => candidate.group_key === 'builtin:file');
const before = ['orphan_tool', 'write_file', 'exec_command'];
const snapshot = JSON.stringify(before);
const checked = api.applyGroupSelection(before, fileCandidates, true);
const unchecked = api.applyGroupSelection(checked, fileCandidates, false);
const deduped = api.applyGroupSelection(['write_file', 'write_file'], fileCandidates, true);
return {{
  checked,
  unchecked,
  deduped,
  inputUntouched: JSON.stringify(before) === snapshot,
  returnedNewArray: checked !== before,
}};
"""
    )
    assert result["checked"] == [
        "orphan_tool",
        "write_file",
        "exec_command",
        "edit_file",
        "apply_patch",
        "read_file",
    ], "原有项保持原序，新增别名按候选顺序追加"
    assert result["unchecked"] == ["orphan_tool", "exec_command"], "取消只移除组内别名"
    assert result["deduped"] == ["write_file", "edit_file", "apply_patch", "read_file"]
    assert result["inputUntouched"] is True
    assert result["returnedNewArray"] is True


def test_filter_sub_groups_matches_any_field_and_returns_input_when_empty():
    """group_key / group / id / label / description 任一命中即保留该子组；空查询原样返回。"""
    result = _run_typescript(
        f"""
const groups = api.groupCandidates({json.dumps(CANDIDATES)});
const keys = (query) => api.filterSubGroups(groups, query).map((group) => group.key);
return {{
  byGroupKey: keys('mcp:'),
  byGroupLabel: keys('履约罚款'),
  byCandidateId: keys('read_file'),
  byCandidateLabel: keys('发送邮件'),
  byDescription: keys('沙箱'),
  caseInsensitive: keys('JIRA_SEARCH'),
  blank: keys('   '),
  noMatch: keys('不存在的工具'),
  allKeys: groups.map((group) => group.key),
}};
"""
    )
    assert result["byGroupKey"] == ["mcp:jira"]
    assert result["byGroupLabel"] == ["api:履约罚款"]
    assert result["byCandidateId"] == ["builtin:file"]
    assert result["byCandidateLabel"] == ["api:履约罚款"]
    assert result["byDescription"] == ["builtin:sandbox"]
    assert result["caseInsensitive"] == ["mcp:jira"]
    assert result["blank"] == result["allKeys"], "空查询原样返回"
    assert result["noMatch"] == []


def test_find_orphan_ids_keeps_aliases_of_known_candidates_out_of_the_history_area():
    """缺陷 A 回归：勾选一个能力会写入整组别名（write_file → edit_file/apply_patch），
    这些别名不属于任何候选的 id，但**不是**「历史遗留」——它们必须留在原分组里继续显示，
    只有"目录里完全查不到"的名字才进历史区。"""
    result = _run_typescript(
        f"""
const candidates = {json.dumps(CANDIDATES)};
return {{
  aliasOnly: api.findOrphanIds(['write_file', 'edit_file', 'apply_patch'], candidates),
  realOrphan: api.findOrphanIds(['write_file', 'edit_file', 'removed_mcp_tool'], candidates),
  emptyCatalog: api.findOrphanIds(['write_file'], []),
}};
"""
    )

    assert result["aliasOnly"] == [], "别名被误判成历史遗留项（截图里 Write/Edit 就是这么来的）"
    assert result["realOrphan"] == ["removed_mcp_tool"]
    # 目录还没加载出来（或加载失败）时不能吞掉已配置项，否则用户无法解除
    assert result["emptyCatalog"] == ["write_file"]
