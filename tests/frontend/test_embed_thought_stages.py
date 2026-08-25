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


SAMPLE_LOGS = [
    {"title": "智能路由决策", "category": "router", "status": "pending"},
    {"title": "分析用户请求并进行意图识别", "category": "intent", "status": "success"},
    {"title": "模型调用: DeepSeek-V3.2", "category": "llm", "status": "success"},
]


def test_embed_thought_summary_title_uses_business_progress_not_model_names():
    result = _run_typescript(
        "frontend/src/utils/embedThoughtStages.ts",
        f"""
const logs = {json.dumps(SAMPLE_LOGS, ensure_ascii=False)};
return {{
  thinking: api.getEmbedThoughtSummaryTitle({{ logs, isThinking: true, thinkingText: '', turnType: 'general' }}),
  done: api.getEmbedThoughtSummaryTitle({{ logs, isThinking: false, thinkingText: '', turnType: 'general' }}),
  emptyThinking: api.getEmbedThoughtSummaryTitle({{ logs: [], isThinking: true, thinkingText: '', turnType: 'general' }}),
}};
""",
    )

    assert "DeepSeek" not in result["thinking"]
    assert result["thinking"] in {
        "正在理解问题…",
        "正在选择处理方式…",
        "正在调用工具…",
        "正在生成回答…",
        "思考中…",
    }
    assert result["done"] == "执行完成"
    assert result["emptyThinking"] == "思考中…"


def test_embed_thought_summary_lives_in_shared_timeline_header():
    embed = (ROOT / "frontend/src/views/EmbedChat.vue").read_text(encoding="utf-8")
    debug = (ROOT / "frontend/src/views/AgentDebug.vue").read_text(encoding="utf-8")
    timeline = (ROOT / "frontend/src/components/chat/ChatExecutionTimeline.vue").read_text(encoding="utf-8")

    assert "<ChatExecutionTimeline" in embed
    assert "<ChatExecutionTimeline" in debug
    assert "getEmbedThoughtSummaryTitle" not in embed
    assert "getDisplayLogs(msg)" not in embed
    assert "getThoughtStages" not in embed
    assert "buildEmbedThoughtStages" not in embed
    assert 'props.hasAnswer ? "执行完成" : "执行过程"' in timeline


def test_chat_thinking_header_and_timeline_copy_contract():
    header = (ROOT / "frontend/src/components/chat/ChatThinkingHeader.vue").read_text(encoding="utf-8")
    timeline = (ROOT / "frontend/src/components/chat/ChatExecutionTimeline.vue").read_text(encoding="utf-8")

    assert "showCopy" in header
    assert "isCopied" in header
    assert '@click.stop="emit(\'copy\')"' in header
    assert "复制思考内容" in header
    assert "已复制" in header

    assert ":show-copy=" in timeline
    assert ":is-copied=" in timeline
    assert '@copy="handleCopyAll"' in timeline
    assert "fullTimelineText" in timeline
    assert "handleCopyAll" in timeline


def test_chat_thinking_header_places_copy_after_title_before_step_badge():
    header = (ROOT / "frontend/src/components/chat/ChatThinkingHeader.vue").read_text(encoding="utf-8")

    title_at = header.index("{{ title }}")
    copy_at = header.index('v-if="showCopy"')
    steps_at = header.index('v-if="stepCount > 0"')

    assert title_at < copy_at < steps_at


def test_route_progress_contract_uses_router_category_and_stable_ids():
    embed = (ROOT / "frontend/src/views/EmbedChat.vue").read_text(encoding="utf-8")
    timeline = (ROOT / "frontend/src/components/chat/ChatExecutionTimeline.vue").read_text(encoding="utf-8")

    assert 'data.id || Date.now() + Math.random()' in embed
    assert 'existingIdx = msg.logs.findIndex((l) => l.id === logId)' in embed
    assert 'category: "router"' in embed or 'category === "router"' in embed
    assert 'item.title.includes("获取可用专家")' in timeline
    assert 'item.status === "pending"' in timeline


def test_embed_router_completion_reuses_target_selection_log():
    embed = (ROOT / "frontend/src/views/EmbedChat.vue").read_text(encoding="utf-8")

    assert 'const routerId = data.id || "route:target_selection";' in embed
    assert 'id: "router_" + Date.now()' not in embed
    assert 'preserveRouteSelectionDuration' in embed
    assert '外层目标配置解析总耗时' in embed
    assert 'preserveRouteSelectionTitle' in embed


def test_embed_router_completion_does_not_render_internal_router_thought():
    embed = (ROOT / "frontend/src/views/EmbedChat.vue").read_text(encoding="utf-8")

    assert "已完成目标专家匹配" in embed
    assert "思考过程:\\n${thoughtText}" not in embed


def test_embed_resume_router_completion_uses_deduplicating_log_upsert():
    embed = (ROOT / "frontend/src/views/EmbedChat.vue").read_text(encoding="utf-8")

    router_branch = embed.split('} else if (data.type === "router_log") {', 2)[2]
    router_branch = router_branch.split('} else if (applyChatBIInsightEvent', 1)[0]
    assert "addEmbedLogFromStream(agentMsg.value" in router_branch
    assert "agentMsg.value.logs.push" not in router_branch
