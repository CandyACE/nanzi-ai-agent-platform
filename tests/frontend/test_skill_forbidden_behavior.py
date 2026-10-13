"""公共技能「管理员已禁用」判定的纯函数行为。

三处挂载入口（会话输入框技能中心、会话固定资源弹窗、任务提示词编辑器）共用这一份判定，
所以直接在 node harness 里跑真实 TypeScript 实现，不挂载组件——组件只管渲染。

重点钉住两件事：
1. 只有严格布尔 `true` 才算被禁。后端清单接口下发的是布尔值，但个人技能接口不带该字段，
   旧缓存 / 旧后端也可能没有；若写成真值判断，`forbidden: 'false'`（当字符串用时是真值）
   会把本来可用的技能误锁成不可选。
2. 原因文案随动作切换，未禁用时返回空串，调用方据此决定要不要挂 title。
"""

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE = "frontend/src/utils/skillForbidden.ts"
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


def test_only_strict_boolean_true_is_treated_as_forbidden():
    """`forbidden: true` 为真；缺失 / false / undefined / null / 字符串 / 数字一律为假。"""
    result = _run_typescript(
        """
return {
  forbiddenTrue: api.isSkillForbidden({ id: 's1', forbidden: true }),
  forbiddenFalse: api.isSkillForbidden({ id: 's2', forbidden: false }),
  missingField: api.isSkillForbidden({ id: 's3' }),
  explicitUndefined: api.isSkillForbidden({ id: 's4', forbidden: undefined }),
  explicitNull: api.isSkillForbidden({ id: 's5', forbidden: null }),
  stringTrue: api.isSkillForbidden({ id: 's6', forbidden: 'true' }),
  stringFalse: api.isSkillForbidden({ id: 's7', forbidden: 'false' }),
  numericOne: api.isSkillForbidden({ id: 's8', forbidden: 1 }),
  emptyObject: api.isSkillForbidden({}),
  nullSkill: api.isSkillForbidden(null),
  undefinedSkill: api.isSkillForbidden(undefined),
  missingArgument: api.isSkillForbidden(),
};
"""
    )

    assert result["forbiddenTrue"] is True
    for key in (
        "forbiddenFalse",
        "missingField",
        "explicitUndefined",
        "explicitNull",
        "stringTrue",
        "stringFalse",
        "numericOne",
        "emptyObject",
        "nullSkill",
        "undefinedSkill",
        "missingArgument",
    ):
        assert result[key] is False, f"{key} 不该被判定为禁用（缺字段按「未禁用」处理）"


def test_forbidden_reason_is_action_aware_and_empty_for_available_skills():
    """原因文案给「为什么不能点」：未禁用为空串，已禁用随动作动词变化。"""
    result = _run_typescript(
        """
return {
  forbiddenDefault: api.forbiddenSkillReason({ id: 's1', forbidden: true }),
  forbiddenMount: api.forbiddenSkillReason({ id: 's1', forbidden: true }, '挂载'),
  forbiddenCheck: api.forbiddenSkillReason({ id: 's1', forbidden: true }, '勾选'),
  available: api.forbiddenSkillReason({ id: 's2', forbidden: false }),
  missingField: api.forbiddenSkillReason({ id: 's3' }),
  nullSkill: api.forbiddenSkillReason(null),
  badge: api.FORBIDDEN_SKILL_BADGE,
};
"""
    )

    assert result["badge"] == "管理员已禁用"
    for key in ("forbiddenDefault", "forbiddenMount", "forbiddenCheck"):
        assert "管理员已禁用" in result[key], f"{key} 必须写明禁用原因"
    assert result["forbiddenDefault"] == "管理员已禁用该技能，无法挂载", "默认动作是「挂载」"
    assert result["forbiddenMount"] == result["forbiddenDefault"]
    assert result["forbiddenCheck"] == "管理员已禁用该技能，无法勾选", "资源网格里动作是「勾选」"
    assert result["available"] == ""
    assert result["missingField"] == "", "缺字段（旧接口 / 个人技能）不产生任何提示"
    assert result["nullSkill"] == ""


def test_judgement_stays_usable_for_wide_skill_objects():
    """技能的其它字段（个人技能、描述、路径）不得影响判定，避免「看着像技能」就误判。"""
    result = _run_typescript(
        """
return {
  personal: api.isSkillForbidden({ id: 'p1', name: '我的技能', scope: 'personal', path: '/tmp/p1' }),
  global: api.isSkillForbidden({ id: 'g1', name: '公共技能', scope: 'global', forbidden: true }),
  truthyDescription: api.isSkillForbidden({ id: 'g2', description: 'forbidden', name: 'forbidden' }),
};
"""
    )

    assert result["personal"] is False, "个人技能接口不下发该字段，永远可用"
    assert result["global"] is True
    assert result["truthyDescription"] is False, "名字/描述里出现 forbidden 字样不算禁用"
