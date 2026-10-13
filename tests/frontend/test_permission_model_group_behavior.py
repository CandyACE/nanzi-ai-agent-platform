"""权限弹窗「可用模型」页的分组纯函数。

模型动辄几十条，已勾选项若混在原序里就被淹没。分组规则：
- `selected`：全部已勾选模型，按原顺序，**无论是否匹配搜索词都保留**（否则用户会以为白名单丢了）；
- `others`：未勾选且匹配搜索词的模型，按原顺序；搜索词为空时就是全部未勾选项。

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


def _group(query: str = "", selected_js: str = "[]", models_js: str | None = None):
    models_js = models_js if models_js is not None else MODELS
    result = _run_typescript(
        f"return api.groupPermissionModels({models_js}, {json.dumps(query)}, {selected_js});"
    )
    return {
        "selected": [row["id"] for row in result["selected"]],
        "others": [row["id"] for row in result["others"]],
    }


MODELS = json.dumps(
    [
        {"id": "gpt-4o", "name": "GPT-4o", "description": "gpt-4o"},
        {"id": "deepseek-chat", "name": "DeepSeek Chat", "description": "deepseek-chat"},
        {"id": "qwen-vl-max", "name": "Qwen VL Max", "description": "qwen-vl-max"},
    ],
    ensure_ascii=False,
)


def test_without_query_selected_comes_first_and_keeps_order():
    groups = _group("", json.dumps(["qwen-vl-max", "gpt-4o"]))

    assert groups["selected"] == ["gpt-4o", "qwen-vl-max"]  # 按列表原序，不是勾选顺序
    assert groups["others"] == ["deepseek-chat"]


def test_without_selection_everything_is_in_others():
    groups = _group("")

    assert groups["selected"] == []
    assert groups["others"] == ["gpt-4o", "deepseek-chat", "qwen-vl-max"]


def test_when_everything_is_selected_others_is_empty():
    groups = _group("", json.dumps(["gpt-4o", "deepseek-chat", "qwen-vl-max"]))

    assert groups["selected"] == ["gpt-4o", "deepseek-chat", "qwen-vl-max"]
    assert groups["others"] == []


def test_query_filters_others_by_display_name():
    groups = _group("deepseek")

    assert groups["others"] == ["deepseek-chat"]


def test_query_filters_others_by_model_id():
    groups = _group("qwen-vl")

    assert groups["others"] == ["qwen-vl-max"]


def test_query_is_case_insensitive_and_trimmed():
    groups = _group("  GPT-4O  ")

    assert groups["others"] == ["gpt-4o"]


def test_selected_stays_visible_even_when_it_does_not_match_query():
    """搜索时也不能把已选项藏起来，否则用户会以为白名单丢了。"""
    groups = _group("gpt-4o", json.dumps(["deepseek-chat"]))

    assert groups["selected"] == ["deepseek-chat"]
    assert groups["others"] == ["gpt-4o"]


def test_selected_and_matching_item_is_not_duplicated():
    groups = _group("gpt-4o", json.dumps(["gpt-4o"]))

    assert groups["selected"] == ["gpt-4o"]
    assert groups["others"] == []


def test_does_not_mutate_input_array():
    mutated = _run_typescript(
        f"""
const input = {MODELS};
api.groupPermissionModels(input, "gpt", []);
return {{ length: input.length, first: input[0].id }};
"""
    )
    assert mutated == {"length": 3, "first": "gpt-4o"}


def test_handles_null_input():
    groups = _group("gpt", "[]", "null")

    assert groups == {"selected": [], "others": []}
