"""输入框候选决策纯函数：版本开关 × 白名单候选。

候选**只来自白名单**（后端 scope=chat 已过滤），不再把智能体默认模型单列成一个可选项——
下拉第一项固定是「使用默认模型」（= 不覆盖，跟随智能体/平台默认），单列一份是重复的。
只要白名单候选 ≥1（下拉里「使用默认模型」+ 至少一个模型 = ≥2 项可选）就显示切换器；
候选为空（勾选的模型全被停用）时隐藏并给提示，而不是变成一个点开是空的框。

用仓库既有的 node transpile harness 直接跑 `frontend/src/utils/modelSelect.ts`。
"""

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.no_infrastructure

MODULE = "frontend/src/utils/modelSelect.ts"


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


def _decide(**kwargs):
    payload = json.dumps({"versionAllowsSwitch": True, "chatModels": [], **kwargs})
    return _run_typescript(f"return api.resolveChatModelSwitch({payload});")


def _models(*ids):
    return [
        {"model_id": mid, "name": f"{mid}-名称", "type": "llm", "is_active": True}
        for mid in ids
    ]


def test_version_forbids_switch_hides_control():
    assert _decide(versionAllowsSwitch=False, chatModels=_models("a"))["visible"] is False


def test_unconfigured_whitelist_returns_all_candidates():
    decision = _decide(chatModels=_models("a", "b", "c"))
    assert decision["visible"] is True
    assert [o["value"] for o in decision["options"]] == ["a", "b", "c"]


def test_agent_default_model_is_never_listed_as_a_candidate():
    """即使调用方仍传 agentDefaultModel，也不得把它变成候选项（下拉已有「使用默认模型」）。"""
    decision = _decide(chatModels=_models("b", "c"), agentDefaultModel="a")

    assert [o["value"] for o in decision["options"]] == ["b", "c"]
    assert all(not o.get("isAgentDefault") for o in decision["options"])


def test_single_candidate_keeps_control_visible():
    """白名单只有一个模型时仍要显示：用户需要在「使用默认模型」与它之间切换。"""
    decision = _decide(chatModels=_models("a"))

    assert decision["visible"] is True
    assert [o["value"] for o in decision["options"]] == ["a"]


def test_multiple_candidates_keep_control_visible():
    decision = _decide(chatModels=_models("b", "a"))

    assert decision["visible"] is True
    assert [o["value"] for o in decision["options"]] == ["b", "a"]


def test_duplicate_candidates_are_deduped():
    decision = _decide(chatModels=_models("a", "a", "b"))

    assert [o["value"] for o in decision["options"]] == ["a", "b"]


def test_empty_candidates_hide_with_hint_instead_of_disappearing():
    decision = _decide(chatModels=[])

    assert decision["visible"] is False
    assert "停用" in decision["emptyHint"] or "管理员" in decision["emptyHint"]
