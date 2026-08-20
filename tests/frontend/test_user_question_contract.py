"""Contract tests for the user question card and receipt helpers."""
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


def test_user_question_parser_and_receipt_contract():
    result = _run_typescript(
        "frontend/src/utils/userQuestion.ts",
        """
const parsed = api.parseUserQuestionEvent({
  type: 'user_question',
  question_id: 'uq_1',
  question: '按什么维度统计？',
  options: [{ id: 'daily', label: '按天' }, { id: 'monthly', label: '按月' }],
  is_multi_select: false,
  allow_custom_input: true,
  context: '销售数据',
});
return {
  parsed,
  receipt: api.buildUserQuestionUserMessage('uq_1', ['monthly'], '排除退款', false, '按什么维度统计？', [{ id: 'daily', label: '按天' }, { id: 'monthly', label: '按月' }]),
  cancelledReceipt: api.buildUserQuestionUserMessage('uq_1', [], '', true, '按什么维度统计？'),
};
""",
    )
    assert result["parsed"]["question_id"] == "uq_1"
    assert result["parsed"]["options"][1]["id"] == "monthly"
    assert result["receipt"].startswith("【用户回答】")
    assert "问题: 按什么维度统计？" in result["receipt"]
    assert "所选选项: 按月 (monthly)" in result["receipt"]
    assert "question_id: uq_1" in result["receipt"]
    assert 'selected_option_ids: ["monthly"]' in result["receipt"]
    assert "排除退款" in result["receipt"]
    assert "cancelled: true" in result["cancelledReceipt"]
    assert "停止当前任务" in result["cancelledReceipt"]


def test_user_question_frontend_wiring_is_independent_from_business_confirmation():
    card = (ROOT / "frontend/src/components/UserQuestionCard.vue").read_text(encoding="utf-8")
    handlers = (ROOT / "frontend/src/utils/agentscopeSseHandlers.ts").read_text(encoding="utf-8")
    embed = (ROOT / "frontend/src/views/EmbedChat.vue").read_text(encoding="utf-8")
    debug = (ROOT / "frontend/src/views/AgentDebug.vue").read_text(encoding="utf-8")

    assert "UserQuestionCard" in card
    assert "is_multi_select" in card
    assert "allow_custom_input" in card
    assert 'case "user_question"' in handlers
    assert "handleUserQuestion" in handlers
    assert "UserQuestionCard" in embed
    assert "UserQuestionCard" in debug
    assert "取消提问" in card
    assert "cancelled" in card
    assert "BusinessConfirmationCard" not in card


def test_cards_collapsible_and_toggle_contract():
    card = (ROOT / "frontend/src/components/UserQuestionCard.vue").read_text(encoding="utf-8")
    biz_card = (ROOT / "frontend/src/components/BusinessConfirmationCard.vue").read_text(encoding="utf-8")
    embed = (ROOT / "frontend/src/views/EmbedChat.vue").read_text(encoding="utf-8")
    debug = (ROOT / "frontend/src/views/AgentDebug.vue").read_text(encoding="utf-8")

    # UserQuestionCard 折叠支持
    assert "toggleExpand" in card
    assert "rotate-180" in card
    assert "expanded" in card

    # BusinessConfirmationCard 折叠支持
    assert "toggleExpand" in biz_card
    assert "rotate-180" in biz_card
    assert "expanded" in biz_card

    # EmbedChat 与 AgentDebug 中的工具确认框与外部执行框折叠支持
    assert "msg.pendingPermission.expanded" in embed
    assert "msg.pendingExternalExecution.expanded" in embed
    assert "msg.pendingPermission.expanded" in debug
    assert "msg.pendingExternalExecution.expanded" in debug

