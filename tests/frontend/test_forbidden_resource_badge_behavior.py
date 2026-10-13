"""禁用资源徽标的计数口径（用户视角的条目数），纯函数行为测试。

为什么不能直接用 `forbidden_tools.length`：勾一个内置能力会写入整组别名
（`write_file` → `edit_file` / `apply_patch`），数组长度于是虚高成 2～3 倍，
用户看到「禁用工具 7 个」但界面上只勾了 3 个勾。口径改为「候选（别名组）粒度」：
一个选中项如果落在某个候选的别名组里，整组只算 1；完全不在任何候选别名里的散项各算 1。

两个页面（用户页 / 角色页）必须共用这一份实现——各写一份必然漂移成两个数字。
"""

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE = "frontend/src/utils/forbiddenResourceBadge.ts"
pytestmark = pytest.mark.no_infrastructure

# 多模块 harness：badge 模块会 import 同目录的 forbiddenToolGroups / forbiddenCommands，
# 单文件 harness 的 require 解析不了 `./xxx`（没有扩展名也没有转译产物），
# 所以这里带一个把相对路径映射回转译内存模块的 require。
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
    script = (
        HARNESS.replace("__MODULE__", json.dumps(MODULE))
        .replace("__EXPRESSION__", expression)
    )
    completed = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


# 与后端 forbidden-catalog 的形状一致：一个候选可能带多个别名（勾一次写一整组）。
CANDIDATES = [
    {"id": "exec_command", "label": "执行终端命令", "description": "", "aliases": ["exec_command"]},
    {"id": "write_file", "label": "写入/修改文件", "description": "", "aliases": ["write_file", "edit_file", "apply_patch"]},
    {"id": "read_file", "label": "读取文件", "description": "", "aliases": ["read_file"]},
]
SKILLS = [
    {"id": "skill:report", "label": "报表生成", "description": ""},
    {"id": "skill:translate", "label": "翻译", "description": ""},
]


def test_whole_alias_group_counts_as_one_entry():
    """整组别名被写入（勾了「写入/修改文件」）时只算 1 条，不按数组长度算 3 条。"""
    result = _run_typescript(
        f"""
const candidates = {json.dumps(CANDIDATES)};
return {{
  fullGroup: api.countSelectedEntries(['write_file', 'edit_file', 'apply_patch'], candidates),
  singleAliasOnly: api.countSelectedEntries(['apply_patch'], candidates),
  aliasPlusNeighbour: api.countSelectedEntries(['edit_file', 'read_file'], candidates),
}};
"""
    )

    assert result["fullGroup"] == 1, "整组别名 = 用户视角的 1 个条目"
    assert result["singleAliasOnly"] == 1, "命中任一别名即代表该候选被选中"
    assert result["aliasPlusNeighbour"] == 2


def test_orphan_entries_and_dedup():
    """不在任何候选别名里的散项（历史遗留 / 后端手写的名字）各算 1，重复项不膨胀。"""
    result = _run_typescript(
        f"""
const candidates = {json.dumps(CANDIDATES)};
return {{
  orphans: api.countSelectedEntries(['legacy_a', 'legacy_b'], candidates),
  mixed: api.countSelectedEntries(['write_file', 'edit_file', 'legacy_a'], candidates),
  duplicates: api.countSelectedEntries(['read_file', 'read_file', 'legacy_a', 'legacy_a'], candidates),
  unknownCatalog: api.countSelectedEntries(['write_file', 'edit_file'], []),
}};
"""
    )

    assert result["orphans"] == 2
    assert result["mixed"] == 2, "整组 1 + 散项 1"
    assert result["duplicates"] == 2
    assert result["unknownCatalog"] == 2, "目录未知时无从判断别名关系，退化为去重计数"


def test_bad_data_is_tolerated_as_empty():
    """坏数据（null / 非数组 / 空串元素）一律按空处理，不得抛错也不得虚增。"""
    result = _run_typescript(
        f"""
const candidates = {json.dumps(CANDIDATES)};
return {{
  nullSelected: api.countSelectedEntries(null, candidates),
  undefinedSelected: api.countSelectedEntries(undefined, candidates),
  stringSelected: api.countSelectedEntries('write_file', candidates),
  nullCandidates: api.countSelectedEntries(['read_file'], null),
  blankItems: api.countSelectedEntries(['', '  '], candidates),
  nullCandidatesInList: api.countSelectedEntries(['read_file'], [null]),
}};
"""
    )

    assert result["nullSelected"] == 0
    assert result["undefinedSelected"] == 0
    assert result["stringSelected"] == 0, "非数组输入不得被当成字符序列逐个计数"
    assert result["nullCandidates"] == 1
    assert result["blankItems"] == 0
    assert result["nullCandidatesInList"] == 1


def test_skills_fall_back_to_id_when_candidates_have_no_aliases():
    """公共技能候选只给 id，没有别名概念：每个技能各算 1。"""
    result = _run_typescript(
        f"""
const skills = {json.dumps(SKILLS)};
return {{
  two: api.countSelectedEntries(['skill:report', 'skill:translate'], skills),
  one: api.countSelectedEntries(['skill:report'], skills),
}};
"""
    )

    assert result["two"] == 2
    assert result["one"] == 1


def test_badge_total_is_tools_plus_commands_plus_skills():
    """徽标总数 = 工具条目数 + 命令解析后的条目数 + 技能条目数；分隔符用 F9 的同一份解析。"""
    result = _run_typescript(
        f"""
const candidates = {json.dumps(CANDIDATES)};
const skills = {json.dumps(SKILLS)};
return {{
  total: api.countForbiddenResourceBadge({{
    forbiddenTools: ['write_file', 'edit_file', 'apply_patch', 'legacy_a'],
    toolCandidates: candidates,
    forbiddenCommandsText: 'rm，shutdown、mv',
    forbiddenSkills: ['skill:report'],
    skillCandidates: skills,
  }}),
  empty: api.countForbiddenResourceBadge({{}}),
  badData: api.countForbiddenResourceBadge({{
    forbiddenTools: null,
    toolCandidates: null,
    forbiddenCommandsText: null,
    forbiddenSkills: null,
    skillCandidates: null,
  }}),
  commandsOnly: api.countForbiddenResourceBadge({{ forbiddenCommandsText: 'rm, shutdown' }}),
}};
"""
    )

    assert result["total"] == 2 + 3 + 1, "工具（整组 1 + 散项 1）+ 命令 3 + 技能 1"
    assert result["empty"] == 0
    assert result["badData"] == 0
    assert result["commandsOnly"] == 2


def test_badge_implementation_lives_in_one_shared_module():
    """计数口径必须是单一来源：两个页面只调用它，不得各自内联 length 相加。"""
    source = (ROOT / MODULE).read_text(encoding="utf-8")

    assert "export function countForbiddenResourceBadge(" in source
    assert "from './forbiddenToolGroups'" in source
    assert "from './forbiddenCommands'" in source

    users = (ROOT / "frontend/src/views/Users.vue").read_text(encoding="utf-8")
    roles = (ROOT / "frontend/src/views/Roles.vue").read_text(encoding="utf-8")
    for name, page in (("Users.vue", users), ("Roles.vue", roles)):
        assert "countForbiddenResourceBadge" in page, f"{name} 必须复用共享计数函数"
        assert "forbidden_tools?.length" not in page, f"{name} 不得再用数组长度当禁用工具数"
