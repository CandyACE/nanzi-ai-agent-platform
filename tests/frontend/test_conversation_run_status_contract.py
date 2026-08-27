import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.no_infrastructure


def _run_typescript(expression: str):
    module_path = "frontend/src/composables/chat/useConversationRunStatus.ts"
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
  ? {{ ref: value => ({{ value }}), onUnmounted: () => {{}} }}
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


def test_run_status_controller_ignores_stale_conversation_results_and_cleans_up():
    result = _run_typescript(
        """
let resolveOld;
let resolveNew;
const fetchStatus = id => new Promise(resolve => {
  if (id === 'old') resolveOld = resolve;
  else resolveNew = resolve;
});
const controller = api.createConversationRunStatusController(fetchStatus, 100000);
const oldRequest = controller.refresh('old');
const newRequest = controller.refresh('new');
resolveOld({ active: true, trace_id: 'old-trace', ttl_seconds: 20 });
await oldRequest;
const afterOld = controller.remoteRunActive.value;
resolveNew({ active: false, trace_id: null, ttl_seconds: null });
await newRequest;
const afterNew = controller.remoteRunActive.value;
controller.startPolling('new');
controller.stopPolling();
return { afterOld, afterNew, stopped: controller.isPolling() === false };
""",
    )
    assert result == {"afterOld": False, "afterNew": False, "stopped": True}


def test_both_chat_surfaces_refresh_remote_status_on_visibility_and_bind_busy_states():
    for relative_path in (
        "frontend/src/views/EmbedChat.vue",
        "frontend/src/views/AgentDebug.vue",
    ):
        source = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "useConversationRunStatus" in source
        assert "run-status" in source
        assert "refreshCurrentRunStatus" in source
        assert "visibilitychange" in source
        assert ':is-processing="isProcessing || remoteRunActive"' in source
        assert ':is-submitting="sendLocked"' in source
        assert "if (isProcessing.value || remoteRunActive.value) return;" in source
