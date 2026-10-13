"""上下文计量修正的前端契约（见 spec §4.9）。

两条独立修正都要被锁住：

- **P1**：窗口/预算类数值统一走 `formatContextTokens`（2 的幂感知：262144 → 256k），
  用量计数器继续走十进制 `formatTokens`（累计 tok 数不会因为窗口口径被改小）；
- **P2**：浮标与面板显示 `current_tokens`（后端按最近一次调用实测校准），
  并在校准生效时给出用户可见的说明，而不是继续把纯估算值当真实占用。
"""

from pathlib import Path

import json
import subprocess

import pytest

pytestmark = pytest.mark.no_infrastructure

ROOT = Path(__file__).resolve().parents[2]
CONTEXT_USAGE_MODULE = "frontend/src/composables/useContextUsage.ts"
CONTEXT_USAGE = (ROOT / CONTEXT_USAGE_MODULE).read_text(encoding="utf-8")
CHAT_INPUT = (ROOT / "frontend/src/components/embed/ChatInput.vue").read_text(encoding="utf-8")
STATS_MODAL = (
    ROOT / "frontend/src/components/chat/ChatModelCallStatsModal.vue"
).read_text(encoding="utf-8")


def _format_context_tokens(values: list[int]) -> list[str]:
    """直接跑真实实现（该模块 import vue/axios，harness 里把它们 mock 掉）。"""
    script = f"""
(async () => {{
const fs = require('fs');
const ts = require('./frontend/node_modules/typescript');
const source = fs.readFileSync({json.dumps(CONTEXT_USAGE_MODULE)}, 'utf8');
const code = ts.transpileModule(source, {{
  compilerOptions: {{ module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 }}
}}).outputText;
const moduleRef = {{ exports: {{}} }};
const mockRequire = (id) => id === 'vue'
  ? {{ ref: (value) => ({{ value }}) }}
  : (id === '@/utils/axios' ? {{ default: {{ get: () => ({{}}) }} }} : require(id));
new Function('module', 'exports', 'require', code)(moduleRef, moduleRef.exports, mockRequire);
const values = {json.dumps(values)};
process.stdout.write(JSON.stringify(values.map((n) => moduleRef.exports.formatContextTokens(n))));
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


def test_format_context_tokens_is_power_of_two_aware():
    """2 的幂窗口按 ÷1024 显示，非 2 的幂预算仍走十进制近似。"""
    assert _format_context_tokens([262144, 253952, 65536]) == ["256k", "248k", "64k"]
    assert _format_context_tokens([8192, 44793, 123498]) == ["8.2k", "45k", "123k"]



def test_context_usage_type_exposes_calibrated_fields():
    """响应新增字段必须进类型，否则模板里拿不到（TS 会当成不存在的属性）。"""
    assert "current_tokens?: number | null" in CONTEXT_USAGE
    assert "calibration?: ContextUsageCalibration | null" in CONTEXT_USAGE
    assert "sample_estimated_tokens" in CONTEXT_USAGE
    assert "sample_actual_tokens" in CONTEXT_USAGE


def test_format_helpers_document_their_split():
    """两个换算函数各写明分工，防止窗口值再次被十进制近似。"""
    assert "2 的幂感知" in CONTEXT_USAGE
    assert "十进制" in STATS_MODAL
    assert "formatContextTokens" in STATS_MODAL


def test_stats_modal_window_and_budget_use_context_scale():
    """窗口/预算的 5 处引用全部切到 formatContextTokens。"""
    assert STATS_MODAL.count("formatContextTokens(stat.request_input_budget)") == 4
    assert (
        STATS_MODAL.count("formatContextTokens(stat.history_budget || stat.context_budget)")
        == 2
    )
    assert STATS_MODAL.count("formatContextTokens(stat.completion_reserve_tokens)") == 1
    # 这三类数值不得再走十进制 formatTokens
    assert "formatTokens(stat.request_input_budget)" not in STATS_MODAL
    assert "formatTokens(stat.history_budget" not in STATS_MODAL
    assert "formatTokens(stat.completion_reserve_tokens)" not in STATS_MODAL


def test_stats_modal_usage_counters_stay_decimal():
    """用量计数器（缓存量、估算占用、实际输入、构成项）保持十进制口径。"""
    assert "const formatTokens = (n: number): string => {" in STATS_MODAL
    assert "formatTokens(statsSummary.totalCacheIn)" in STATS_MODAL
    assert "formatTokens(statsSummary.totalUncached)" in STATS_MODAL
    assert "formatTokens(stat.context_breakdown.total_tokens)" in STATS_MODAL
    assert "formatTokens(stat.input_tokens)" in STATS_MODAL
    assert "formatTokens(item.value)" in STATS_MODAL


def test_chat_input_prefers_calibrated_current_tokens():
    """浮标与面板显示 current_tokens，旧响应缺字段时回落到估算值。"""
    assert "current_tokens ??" in CHAT_INPUT
    assert "estimated_current_tokens" in CHAT_INPUT
    assert "contextCurrentTokens" in CHAT_INPUT
    # 旧的直接读估算字段的写法不得残留
    assert "formatContextTokens(contextUsage.estimated_current_tokens)" not in CHAT_INPUT


def test_chat_input_shows_calibration_note_to_user():
    """校准生效时必须给用户可见说明，不能只写代码注释。"""
    assert "实测校准" in CHAT_INPUT
    assert "contextCalibrationNote" in CHAT_INPUT
    assert "calibration?.applied" in CHAT_INPUT
    # 说明要真的渲染到模板里
    assert 'data-testid="context-usage-calibration-note"' in CHAT_INPUT
