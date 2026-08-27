import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
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
const requireModule = id => id === 'vue'
  ? {{ ref: value => ({{ value }}) }}
  : require(id);
new Function('module', 'exports', 'require', code)(moduleRef, moduleRef.exports, requireModule);
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


def test_chat_send_gate_claims_synchronously_and_releases_all_paths():
    result = _run_typescript(
        "frontend/src/composables/chat/useChatSendGate.ts",
        """
const gate = api.createChatSendGate();
let entered = 0;
let release;
const hold = new Promise(resolve => { release = resolve; });
const first = gate.runExclusive(async () => {
  entered += 1;
  await hold;
  return 'first';
});
const second = await gate.runExclusive(async () => {
  entered += 1;
  return 'second';
});
release();
const firstValue = await first;
const thirdValue = await gate.runExclusive(async () => 'third');
let rejectedEntered = false;
await gate.runExclusive(async () => { throw new Error('expected'); }).catch(() => {});
const afterError = await gate.runExclusive(async () => {
  rejectedEntered = true;
  return 'after-error';
});
return { entered, second: second ?? null, firstValue, thirdValue, rejectedEntered, afterError, locked: gate.locked.value };
""",
    )

    assert result == {
        "entered": 1,
        "second": None,
        "firstValue": "first",
        "thirdValue": "third",
        "rejectedEntered": True,
        "afterError": "after-error",
        "locked": False,
    }
