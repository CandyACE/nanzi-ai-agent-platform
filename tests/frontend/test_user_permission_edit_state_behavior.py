"""用户权限「直配 vs 角色继承」的取数口径（F1 / F3），纯函数行为测试。

背景：用户页原先拿 `permissions`（用户 ∪ 角色的**并集**）回显并整份 PUT 回去，
于是角色级的禁用项被固化成用户级记录——角色页之后取消禁用，该用户仍被禁；
反过来用户在用户页取消角色级禁用也无效却提示成功。

修法：回显与提交都只看 `direct_permissions`（该用户直配项）；`permissions` 只用来
算出"哪些禁用来自角色"，在界面上以只读形式展示。旧后端不返回 `direct_permissions`，
此时必须回退到 `permissions`（否则前端会白屏，或保存时把真实配置整体清空）。
"""

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE = "frontend/src/utils/permissionLists.ts"
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


def _permissions(**overrides):
    lists = {
        "agents": [],
        "datasets": [],
        "metadata": [],
        "apis": [],
        "menus": [],
        "elements": [],
        "forbidden_tools": [],
        "forbidden_commands": [],
        "forbidden_skills": [],
        "models": [],
    }
    lists.update(overrides)
    return lists


# 场景：角色给了 S 技能禁用与 rm 命令禁用，用户自己又直配了 write_file 工具禁用。
EFFECTIVE = _permissions(
    agents=["agent-1"],
    forbidden_tools=["write_file", "edit_file", "apply_patch"],
    forbidden_commands=["rm"],
    forbidden_skills=["skill:report"],
    models=["gpt-4o"],
)
DIRECT = _permissions(
    agents=["agent-1"],
    forbidden_tools=["write_file", "edit_file", "apply_patch"],
    forbidden_commands=[],
    forbidden_skills=[],
    models=["gpt-4o"],
)


def test_direct_permissions_drive_the_editable_state():
    """有 direct_permissions 时：可编辑区 = 直配项；角色来源单独算出来给只读区。"""
    result = _run_typescript(
        f"""
const state = api.resolveUserPermissionEditState({{
  permissions: {json.dumps(EFFECTIVE)},
  direct_permissions: {json.dumps(DIRECT)},
}});
return {{
  directTools: state.direct.forbidden_tools,
  directCommands: state.direct.forbidden_commands,
  directSkills: state.direct.forbidden_skills,
  directAgents: state.direct.agents,
  inheritedTools: state.inherited.forbidden_tools,
  inheritedCommands: state.inherited.forbidden_commands,
  inheritedSkills: state.inherited.forbidden_skills,
  fallback: state.usingEffectiveFallback,
}};
"""
    )

    assert result["directTools"] == ["write_file", "edit_file", "apply_patch"]
    assert result["directCommands"] == [], "命令禁用只来自角色，不得写进可编辑/可提交区"
    assert result["directSkills"] == [], "技能禁用只来自角色，不得写进可编辑/可提交区"
    assert result["directAgents"] == ["agent-1"]
    assert result["inheritedTools"] == []
    assert result["inheritedCommands"] == ["rm"]
    assert result["inheritedSkills"] == ["skill:report"]
    assert result["fallback"] is False


def test_missing_direct_permissions_falls_back_to_effective_for_old_backends():
    """旧后端不返回 direct_permissions：回退成 permissions，且不把任何项误标为「来自角色」。"""
    result = _run_typescript(
        f"""
const state = api.resolveUserPermissionEditState({{ permissions: {json.dumps(EFFECTIVE)} }});
return {{
  tools: state.direct.forbidden_tools,
  commands: state.direct.forbidden_commands,
  skills: state.direct.forbidden_skills,
  inherited: state.inherited,
  fallback: state.usingEffectiveFallback,
}};
"""
    )

    assert result["tools"] == ["write_file", "edit_file", "apply_patch"]
    assert result["commands"] == ["rm"]
    assert result["skills"] == ["skill:report"]
    assert result["inherited"] == {
        "forbidden_tools": [],
        "forbidden_commands": [],
        "forbidden_skills": [],
    }, "无法区分继承时不得凭空造出只读项"
    assert result["fallback"] is True


def test_non_object_direct_permissions_also_falls_back():
    """`direct_permissions` 是 null / 数组 / 字符串等坏形状时同样回退，不得当成空配置。"""
    result = _run_typescript(
        f"""
const payloads = [null, [], 'nope', 0];
return payloads.map((value) => {{
  const state = api.resolveUserPermissionEditState({{
    permissions: {json.dumps(EFFECTIVE)},
    direct_permissions: value,
  }});
  return {{
    skills: state.direct.forbidden_skills,
    fallback: state.usingEffectiveFallback,
  }};
}});
"""
    )

    for entry in result:
        assert entry["skills"] == ["skill:report"], "坏形状不得被当成「用户没有直配项」"
        assert entry["fallback"] is True


def test_bad_lists_are_treated_as_empty():
    """`forbidden_*` 为 null / 字符串等坏数据时按空数组处理，不得抛错也不得清空其他字段。"""
    result = _run_typescript(
        """
const state = api.resolveUserPermissionEditState({
  permissions: { agents: ['a'], forbidden_tools: null, forbidden_commands: 'rm,mv', forbidden_skills: undefined },
  direct_permissions: { agents: ['a'], forbidden_tools: null, forbidden_commands: null, forbidden_skills: null },
});
return {
  agents: state.direct.agents,
  directTools: state.direct.forbidden_tools,
  directCommands: state.direct.forbidden_commands,
  inheritedTools: state.inherited.forbidden_tools,
  inheritedCommands: state.inherited.forbidden_commands,
  emptyPayload: api.resolveUserPermissionEditState(undefined).direct,
  stringifyOk: JSON.stringify(api.normalizePermissionLists({ forbidden_tools: 42 })) !== '',
};
"""
    )

    assert result["agents"] == ["a"]
    assert result["directTools"] == []
    assert result["directCommands"] == []
    assert result["inheritedTools"] == []
    assert result["inheritedCommands"] == []
    assert result["emptyPayload"] == _permissions()
    assert result["stringifyOk"] is True


def test_inherited_diff_keeps_effective_order_and_dedups():
    """角色来源项 = 并集 − 直配，保序、去重；直配里没有的并集项一个都不能漏。"""
    result = _run_typescript(
        """
return api.diffInheritedForbidden(
  { forbidden_tools: ['a', 'b', 'c', 'b'], forbidden_commands: ['rm'], forbidden_skills: [] },
  { forbidden_tools: ['b'], forbidden_commands: [], forbidden_skills: [] },
);
"""
    )

    assert result == {
        "forbidden_tools": ["a", "c"],
        "forbidden_commands": ["rm"],
        "forbidden_skills": [],
    }


def test_payload_builder_only_ships_direct_lists():
    """payload 只含直配项：三个禁用键直接来自 direct，角色来源永远不进 payload。"""
    result = _run_typescript(
        f"""
const state = api.resolveUserPermissionEditState({{
  permissions: {json.dumps(EFFECTIVE)},
  direct_permissions: {json.dumps(DIRECT)},
}});
const payload = api.buildUserPermissionPayload(state.direct, {{
  missingDatasetIds: ['dataset-gone'],
  datasets: ['dataset-gone', 'dataset-ok'],
}});
return {{
  tools: payload.forbidden_tools,
  commands: payload.forbidden_commands,
  skills: payload.forbidden_skills,
  datasets: payload.datasets,
  models: payload.models,
  keys: Object.keys(payload).sort(),
}};
"""
    )

    assert result["commands"] == [], "角色来源的命令禁用不得被写进 payload"
    assert result["skills"] == [], "角色来源的技能禁用不得被写进 payload"
    assert result["tools"] == ["write_file", "edit_file", "apply_patch"]
    assert result["datasets"] == ["dataset-ok"]
    assert result["models"] == ["gpt-4o"]
    assert result["keys"] == sorted(
        [
            "agents",
            "datasets",
            "metadata",
            "apis",
            "menus",
            "elements",
            "forbidden_tools",
            "forbidden_commands",
            "forbidden_skills",
            "models",
        ]
    ), "payload 结构必须与后端 PermissionUpdate 完全一致"
