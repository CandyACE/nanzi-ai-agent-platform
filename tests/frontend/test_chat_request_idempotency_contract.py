import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.no_infrastructure


def _run_typescript(expression: str):
    module_path = "frontend/src/utils/clientRequestId.ts"
    script = f"""
(async () => {{
const fs = require('fs');
const ts = require('./frontend/node_modules/typescript');
const source = fs.readFileSync({json.dumps(module_path)}, 'utf8');
const code = ts.transpileModule(source, {{
  compilerOptions: {{ module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 }}
}}).outputText;
const moduleRef = {{ exports: {{}} }};
new Function('module', 'exports', 'require', code)(moduleRef, moduleRef.exports, id => require(id));
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


def test_request_id_generator_returns_distinct_ids():
    result = _run_typescript(
        """
const first = api.createClientRequestId();
const second = api.createClientRequestId();
return { first, second, distinct: first !== second, bounded: first.length <= 128 && second.length <= 128 };
""",
    )
    assert result["distinct"] is True
    assert result["bounded"] is True


def test_pages_send_the_same_snapshot_id_to_the_completion_endpoint():
    for relative_path in (
        "frontend/src/views/EmbedChat.vue",
        "frontend/src/views/AgentDebug.vue",
    ):
        source = (ROOT / relative_path).read_text(encoding="utf-8")
        snapshot_start = source.index("interface ChatSendSnapshot")
        sender_start = source.index("const sendMessageInternal", snapshot_start)
        sender = source[sender_start:]
        assert "clientRequestId: string" in source[snapshot_start:sender_start]
        assert "client_request_id = snapshot.clientRequestId" in sender
        assert "createClientRequestId()" in source[snapshot_start:sender_start]

