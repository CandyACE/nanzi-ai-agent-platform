"""Contract tests for business data confirmation card wiring."""
from __future__ import annotations

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


def test_business_confirmation_message_builder_includes_prefix_and_snapshot():
    result = _run_typescript(
        "frontend/src/utils/businessConfirmation.ts",
        """
const fields = [
  { key: 'supplier_name', label: '供应商名称', value: '北京神马科技有限公司' },
  { key: 'note', label: '备注', value: '新供应商' },
];
return {
  confirm: api.buildBusinessConfirmationUserMessage(true, 'bc_1', fields),
  cancel: api.buildBusinessConfirmationUserMessage(false, 'bc_1', fields),
  prefix: api.BUSINESS_CONFIRMATION_MESSAGE_PREFIX,
};
""",
    )
    assert result["prefix"] == "【业务确认】"
    assert "【业务确认】用户已确定" in result["confirm"]
    assert "supplier_name" in result["confirm"]
    assert "北京神马科技有限公司" in result["confirm"]
    assert "【业务确认】用户已取消" in result["cancel"]
    assert "不要调用写入类工具" in result["cancel"]


def test_business_confirmation_sse_parser_and_stale_marking():
    result = _run_typescript(
        "frontend/src/utils/businessConfirmation.ts",
        """
const parsed = api.parseBusinessConfirmationEvent({
  type: 'business_confirmation',
  confirmation_id: 'bc_new',
  title: '请确认',
  fields: [{ key: 'a', label: 'A', value: '1' }],
  confirm_label: '确定',
  cancel_label: '取消',
});
const messages = [
  { businessConfirmation: { confirmation_id: 'bc_old', status: 'pending', title: '旧', fields: [], confirm_label: '确定', cancel_label: '取消' } },
  { businessConfirmation: parsed },
];
api.markOtherBusinessConfirmationsStale(messages, 'bc_new');
return {
  ok: !!parsed,
  oldStatus: messages[0].businessConfirmation.status,
  newStatus: messages[1].businessConfirmation.status,
};
""",
    )
    assert result["ok"] is True
    assert result["oldStatus"] == "stale"
    assert result["newStatus"] == "pending"


def test_business_confirmation_frontend_wiring_contract():
    card = (ROOT / "frontend/src/components/BusinessConfirmationCard.vue").read_text(encoding="utf-8")
    handlers = (ROOT / "frontend/src/utils/agentscopeSseHandlers.ts").read_text(encoding="utf-8")
    embed = (ROOT / "frontend/src/views/EmbedChat.vue").read_text(encoding="utf-8")
    debug = (ROOT / "frontend/src/views/AgentDebug.vue").read_text(encoding="utf-8")

    assert "业务数据确认" in card or "请确认以下信息" in card
    assert "emit('submit'" in card or 'emit("submit"' in card or "event: 'submit'" in card
    assert 'case "business_confirmation"' in handlers
    assert "handleBusinessConfirmation" in handlers
    assert "BusinessConfirmationCard" in embed
    assert "submitBusinessConfirmation" in embed
    assert "buildBusinessConfirmationUserMessage" in embed
    assert "BusinessConfirmationCard" in debug
    assert "submitBusinessConfirmation" in debug
    assert "dispatchAgentscopeStreamEvent(agentMsg.value, data, addEmbedLogFromStream, messages.value)" in embed
    assert "dispatchAgentscopeStreamEvent(agentMsg.value, data, addRealLog, messages.value)" in debug