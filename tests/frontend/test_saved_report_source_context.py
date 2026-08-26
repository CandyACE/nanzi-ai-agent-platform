import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
MODULE = "frontend/src/utils/savedReportDefaults.ts"
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


def test_saved_report_source_context_keeps_single_dataset_name():
    result = _run_typescript(
        """
return api.resolveSavedReportSourceContext({
  chatbiInsight: {
    sources: [{ dataset_name: '门店数据集', data_source: 'clickhouse', tables: [] }]
  }
});
"""
    )

    assert result == {
        "data_source": "clickhouse",
        "dataset_id": None,
        "dataset_name": "门店数据集",
    }


def test_saved_report_source_context_does_not_guess_dataset_for_federated_query():
    result = _run_typescript(
        """
return api.resolveSavedReportSourceContext({
  chatbiInsight: {
    sources: [
      { dataset_name: '门店数据集', data_source: 'clickhouse', tables: [] },
      { dataset_name: '订单数据集', data_source: 'mysql', tables: [] }
    ]
  }
});
"""
    )

    assert result["dataset_name"] == ""
    assert result["data_source"] == ""
