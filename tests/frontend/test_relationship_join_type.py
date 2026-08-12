"""实体关系 join_type 归一化与展示标签契约。"""

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE = "frontend/src/utils/relationshipJoinType.ts"
pytestmark = pytest.mark.no_infrastructure


def _run_typescript(module_path: str, expression: str):
    script = f"""
(async () => {{
const fs = require('fs');
const ts = require('./frontend/node_modules/typescript');
const source = fs.readFileSync({json.dumps(module_path)}, 'utf8');
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


def test_normalize_relationship_join_type_aliases():
    result = _run_typescript(
        MODULE,
        """
        return {
          left: api.normalizeRelationshipJoinType('LEFT'),
          oneToMany: api.normalizeRelationshipJoinType('ONE_TO_MANY'),
          oneToManySnake: api.normalizeRelationshipJoinType('one_to_many'),
          manyToOne: api.normalizeRelationshipJoinType('many_to_one'),
          inner: api.normalizeRelationshipJoinType('INNER'),
          oneToOne: api.normalizeRelationshipJoinType('One to One'),
          unknown: api.normalizeRelationshipJoinType('weird'),
          empty: api.normalizeRelationshipJoinType(''),
        };
        """,
    )
    assert result == {
        "left": "left",
        "oneToMany": "left",
        "oneToManySnake": "left",
        "manyToOne": "left",
        "inner": "inner",
        "oneToOne": "one_to_one",
        "unknown": "left",
        "empty": "left",
    }


def test_format_relationship_join_type_label():
    result = _run_typescript(
        MODULE,
        """
        return {
          left: api.formatRelationshipJoinTypeLabel('left'),
          oneToMany: api.formatRelationshipJoinTypeLabel('ONE_TO_MANY'),
          inner: api.formatRelationshipJoinTypeLabel('inner'),
          oneToOne: api.formatRelationshipJoinTypeLabel('one_to_one'),
        };
        """,
    )
    assert result["left"] == "Left · 一对多 (1:N)"
    assert result["oneToMany"] == "Left · 一对多 (1:N)"
    assert result["inner"] == "Inner Join"
    assert result["oneToOne"] == "One to One"


def test_relationship_list_wires_join_type_helpers():
    source = (ROOT / "frontend/src/components/metadata/RelationshipList.vue").read_text(
        encoding="utf-8"
    )
    assert "normalizeRelationshipJoinType" in source
    assert "formatRelationshipJoinTypeLabel" in source
    assert "Left Join · One to Many (1:N)" in source
