# 折叠态「深度思考」摘要与字数 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让会话执行时间线里折叠态的「深度思考」行显示定长摘要（回退句读）与字数胶囊，进行中时摘要尾部跟随，从而把这一行从「只有四个字」变成可读的一行。

**Architecture:** 摘要规则集中在新纯函数模块 `frontend/src/utils/reasoningPreview.ts`，组件只做薄封装调用。摘要完全由 `item.content` 现场派生，不新增数据结构、不改 SSE、不调模型。纯函数用仓库既有 Node + `typescript.transpileModule` harness 直接单测（`tests/frontend/` 下已有多个同型测试）。

**Tech Stack:** Vue 3 + TypeScript + Tailwind CSS 3（前端）；pytest + Node harness（前端契约/行为测试）。

> **本仓库约定（优先于计划模板）：** Agent **不执行 `git commit`**。每个任务末尾给出建议 commit message，由用户自行提交。数据库零改动，不代跑 `./dev.sh`。

**Spec:** `docs/superpowers/specs/2026-10-14-reasoning-collapsed-preview-design.md`

---

## File Structure

| 文件 | 职责 |
| --- | --- |
| `frontend/src/utils/reasoningPreview.ts`（新增） | 唯一职责：把思考正文压平成一行、按口径截成摘要、算可见字数。不依赖 Vue、不依赖 `processTimeline.ts`（内部上下文块剥离由调用方完成） |
| `frontend/src/components/chat/ChatExecutionTimeline.vue`（修改） | 折叠行渲染：接入摘要 + 字数胶囊 + 窄屏让位。只加薄封装，不写业务规则 |
| `tests/frontend/test_reasoning_preview_behavior.py`（新增） | 纯函数行为测试（Node 真跑） |
| `tests/frontend/test_model_thinking_config_contract.py`（修改） | 追加折叠态摘要的源码契约断言 |
| `tests/CHECKLIST.md`（修改） | 交付记录 |

---

## Task 1: 纯函数模块 `reasoningPreview.ts`（TDD）

**Files:**
- Create: `frontend/src/utils/reasoningPreview.ts`
- Test: `tests/frontend/test_reasoning_preview_behavior.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/frontend/test_reasoning_preview_behavior.py`，内容如下（harness 与 `test_timeline_live_step_timer_behavior.py` 同型）：

```python
"""折叠态「深度思考」摘要与字数的纯函数行为契约。

摘要规则（压平 Markdown、定长截断回退句读、进行中尾部跟随、字数口径）必须可单测：
它是纯展示派生数据、不落库，出问题只能靠这里的断言兜住。
这里直接用仓库既有的 node transpile harness 跑 `reasoningPreview.ts`。
"""

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.no_infrastructure

MODULE = "frontend/src/utils/reasoningPreview.ts"


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


def test_preview_constants_match_spec():
    assert _run_typescript(
        """
return {
  max: api.REASONING_PREVIEW_MAX_CHARS,
  min: api.REASONING_PREVIEW_MIN_CHARS,
  minVisible: api.REASONING_CHAR_COUNT_MIN_VISIBLE,
};
"""
    ) == {"max": 80, "min": 40, "minVisible": 10}


def test_flatten_strips_block_markers():
    assert _run_typescript(
        """
return api.flattenReasoningText("### 分析步骤\\n- 先看目录\\n- 再确认命名\\n> 引用一句\\n1. 收尾");
"""
    ) == "分析步骤 先看目录 再确认命名 引用一句 收尾"


def test_flatten_drops_fence_and_rule_lines_but_keeps_inner_text():
    assert _run_typescript(
        """
return api.flattenReasoningText("先看代码\\n```python\\nprint(1)\\n```\\n---\\n再看结果");
"""
    ) == "先看代码 print(1) 再看结果"


def test_flatten_strips_inline_marks_and_link_urls():
    assert _run_typescript(
        """
return api.flattenReasoningText("读 [官方文档](https://example.com/x) 的 **要点** 与 `code`");
"""
    ) == "读 官方文档 的 要点 与 code"


def test_flatten_keeps_underscores_in_identifiers():
    """`_` 系标记刻意不剥离：snake_case 与 dunder 文件名远比 `_斜体_` 常见。"""
    assert _run_typescript(
        """
return api.flattenReasoningText("跑 analyze_md_charts.py 与 __init__.py，还有 *.md");
"""
    ) == "跑 analyze_md_charts.py 与 __init__.py，还有 *.md"


def test_flatten_drops_table_separator_row():
    assert _run_typescript(
        """
return api.flattenReasoningText("| 维度 | 说明 |\\n| --- | --- |\\n| 层级 | 标题树 |");
"""
    ) == "维度 说明 层级 标题树"


def test_head_preview_falls_back_to_sentence_break_above_floor():
    """正文 121 字、句号落在第 61 字 → 收在句号之后。"""
    assert _run_typescript(
        """
const result = api.resolveReasoningPreview("甲".repeat(60) + "。" + "乙".repeat(60));
return { text: result.text, truncated: result.truncated };
"""
    ) == {"text": "甲" * 60 + "。…", "truncated": True}


def test_head_preview_ignores_sentence_break_below_floor():
    """首个句读落在第 20 字（低于 40 下界）→ 不回退，写满 80 字再截断。"""
    assert _run_typescript(
        """
const result = api.resolveReasoningPreview("甲".repeat(20) + "。" + "乙".repeat(99));
return { length: result.text.length, endsWithEllipsis: result.text.endsWith("…") };
"""
    ) == {"length": 81, "endsWithEllipsis": True}


def test_head_preview_hard_cuts_when_no_sentence_break_exists():
    assert _run_typescript(
        """
const result = api.resolveReasoningPreview("甲".repeat(120));
return { length: result.text.length, truncated: result.truncated };
"""
    ) == {"length": 81, "truncated": True}


def test_tail_preview_follows_latest_content_and_retreats_to_boundary():
    """pending 时取尾部，并在尾部窗口内回退到句读之后（不把标点留在开头）。"""
    assert _run_typescript(
        """
const result = api.resolveReasoningPreview("甲".repeat(25) + "。" + "乙".repeat(74), { pending: true });
return { text: result.text, truncated: result.truncated };
"""
    ) == {"text": "…" + "乙" * 74, "truncated": True}


def test_tail_preview_skips_prefix_when_text_is_short():
    assert _run_typescript(
        """
const result = api.resolveReasoningPreview("刚开口想", { pending: true });
return { text: result.text, truncated: result.truncated, charCount: result.charCount };
"""
    ) == {"text": "刚开口想", "truncated": False, "charCount": 4}


def test_short_text_is_returned_whole():
    assert _run_typescript(
        """
const result = api.resolveReasoningPreview("直接给出结论，不做拆分。");
return { text: result.text, truncated: result.truncated, charCount: result.charCount };
"""
    ) == {"text": "直接给出结论，不做拆分。", "truncated": False, "charCount": 12}


def test_empty_and_markup_only_content_yields_empty_preview():
    assert _run_typescript(
        """
const cases = ["", "   \\n\\n  ", "---\\n```py\\n```"];
return cases.map(raw => {
  const result = api.resolveReasoningPreview(raw);
  return { text: result.text, charCount: result.charCount, truncated: result.truncated };
});
"""
    ) == [
        {"text": "", "charCount": 0, "truncated": False},
        {"text": "", "charCount": 0, "truncated": False},
        {"text": "", "charCount": 0, "truncated": False},
    ]


def test_char_count_excludes_marks_and_whitespace():
    assert _run_typescript(
        """
return {
  marked: api.reasoningCharCount("**你好** 世界"),
  plain: api.reasoningCharCount("hello world"),
};
"""
    ) == {"marked": 4, "plain": 10}
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd /Users/chenxiaolong/workspace/nanzi-ai-agent-platform
.venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_reasoning_preview_behavior.py -x -q
```

Expected: FAIL —— `Cannot find module`/`readFileSync` 报错（`reasoningPreview.ts` 尚不存在）。若本机 `.venv/bin/python` 不可用，用 `python -m pytest` 或仓库既有 pytest 入口。

- [ ] **Step 3: 实现纯函数模块**

创建 `frontend/src/utils/reasoningPreview.ts`：

```ts
/**
 * 折叠态「深度思考」摘要与字数口径。
 *
 * 摘要完全由思考正文现场派生：不落库、不走后端、不调模型。规则集中在这里，
 * 便于用仓库既有的 Node harness 直接单测（见
 * tests/frontend/test_reasoning_preview_behavior.py）。
 */

/** 摘要正文字符上限。 */
export const REASONING_PREVIEW_MAX_CHARS = 80;
/** 允许回退到句读的最小长度：短于此长度宁可硬截，也不摘出半行。 */
export const REASONING_PREVIEW_MIN_CHARS = 40;
/** 低于该字数不显示「N 字」胶囊，避免开流瞬间闪一个「1 字」。 */
export const REASONING_CHAR_COUNT_MIN_VISIBLE = 10;

/** 句读字符：头部摘要优先收在这些位置之后。 */
const SENTENCE_BREAKS = "。！？；!?;";
/** 尾部跟随的边界字符：在其之后开切，避免从半个词中间切入。 */
const TAIL_BOUNDARY = /[\s，。；！？、,;!?]/;
/** 尾部跟随的边界搜索窗口（字符数）。 */
const TAIL_BOUNDARY_WINDOW = 12;

export interface ReasoningPreview {
  /** 折叠态展示文本；无可展示内容时为空串。 */
  text: string;
  /** 压平后的可见字符数（已去空白与 Markdown 标记）。 */
  charCount: number;
  /** 摘要是否被截断（决定是否加省略号、是否值得挂 title）。 */
  truncated: boolean;
}

/** 剥离块级 Markdown 标记；围栏行、分割线与表格分隔行整行丢弃。 */
function stripBlockMarkers(line: string): string {
  const trimmed = line.trim();
  if (!trimmed) return "";
  // ``` / ~~~ 代码围栏行
  if (/^(`{3,}|~{3,})/.test(trimmed)) return "";
  // --- / *** / ___ 分割线，以及 | --- | --- | 表格分隔行
  if (/^[|\s:-]*-[|\s:-]*$/.test(trimmed)) return "";
  return trimmed
    .replace(/^#{1,6}\s+/, "")
    .replace(/^[-*+]\s+/, "")
    .replace(/^\d+[.)]\s+/, "")
    .replace(/^>\s?/, "");
}

/** 剥离行内 Markdown 标记，只留文字；刻意不处理 `_` 与单个 `*`。 */
function stripInlineMarkers(text: string): string {
  return text
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/`([^`]*)`/g, "$1")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\|/g, " ");
}

/** 压平 Markdown：去标记、折叠空白，得到一行可读纯文本。 */
export function flattenReasoningText(raw: string): string {
  const source = String(raw ?? "");
  if (!source.trim()) return "";
  return source
    .split(/\r?\n/)
    .map((line) => stripInlineMarkers(stripBlockMarkers(line)))
    .filter((line) => line !== "")
    .join(" ")
    .replace(/\s+/g, " ")
    .trim();
}

/** 可见字符数（压平后去掉全部空白）。 */
export function reasoningCharCount(raw: string): number {
  return flattenReasoningText(raw).replace(/\s/g, "").length;
}

/** 头部截取：写满上限，并在下界以上回退到最近的句读之后。 */
function headPreview(flat: string): string {
  const head = flat.slice(0, REASONING_PREVIEW_MAX_CHARS);
  for (let index = head.length - 1; index >= REASONING_PREVIEW_MIN_CHARS; index -= 1) {
    if (SENTENCE_BREAKS.includes(head[index])) return head.slice(0, index + 1);
  }
  return head;
}

/** 尾部截取：跟随最新内容，并在窗口内回退到边界字符之后。 */
function tailPreview(flat: string): string {
  const tail = flat.slice(-REASONING_PREVIEW_MAX_CHARS);
  const limit = Math.min(TAIL_BOUNDARY_WINDOW, tail.length - 1);
  for (let index = 0; index < limit; index += 1) {
    if (TAIL_BOUNDARY.test(tail[index])) return tail.slice(index + 1);
  }
  return tail;
}

/** 折叠态摘要：pending 时取尾部（跟随最新内容），否则取头部并回退句读。 */
export function resolveReasoningPreview(
  raw: string,
  options: { pending?: boolean } = {},
): ReasoningPreview {
  const flat = flattenReasoningText(raw);
  if (!flat) return { text: "", charCount: 0, truncated: false };
  const charCount = flat.replace(/\s/g, "").length;
  if (flat.length <= REASONING_PREVIEW_MAX_CHARS) {
    return { text: flat, charCount, truncated: false };
  }
  if (options.pending) {
    return { text: `…${tailPreview(flat)}`, charCount, truncated: true };
  }
  return { text: `${headPreview(flat)}…`, charCount, truncated: true };
}
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd /Users/chenxiaolong/workspace/nanzi-ai-agent-platform
.venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_reasoning_preview_behavior.py -q
```

Expected: `14 passed`。

- [ ] **Step 5: 逐个跑变异（关键 3 条）确认测试真的兜得住**

```bash
# M1 去掉下界：headPreview 循环条件改成 index >= 0
# M2 pending 分支改回头部：options.pending ? headPreview : tailPreview 互换
# M3 stripInlineMarkers 里补一行 .replace(/_([^_]+)_/g, "$1")
```

每次改完跑 Step 4 的命令，Expected: 至少一条 FAIL；确认后**还原**。

- [ ] **Step 6: 记录建议提交（由用户执行）**

```bash
git add frontend/src/utils/reasoningPreview.ts tests/frontend/test_reasoning_preview_behavior.py
# 建议 commit message（Agent 不代跑）：
# feat(timeline): 新增折叠态深度思考摘要与字数纯函数及行为测试
```

---

## Task 2: 组件接入折叠行

**Files:**
- Modify: `frontend/src/components/chat/ChatExecutionTimeline.vue`（模板 `:82-95`；脚本 imports `:604` 附近与 `:945` 附近）

- [ ] **Step 1: 加导入**

在 `frontend/src/components/chat/ChatExecutionTimeline.vue` 的 `import { stripInternalContextBlocks } from "@/utils/streamContentSanitize";`（`~:604`）之后新增：

```ts
import {
  REASONING_CHAR_COUNT_MIN_VISIBLE,
  reasoningCharCount,
  resolveReasoningPreview,
  type ReasoningPreview,
} from "@/utils/reasoningPreview";
```

- [ ] **Step 2: 加两个薄封装函数**

在 `function isReasoningBodyOpen(item: ProcessTimelineTextItem): boolean { ... }`（`~:945`）之后新增：

```ts
/** 折叠态摘要；pending 时跟随最新内容。内部上下文块剥离沿用 visibleTimelineText。 */
function reasoningPreviewOf(item: ProcessTimelineTextItem): ReasoningPreview {
  return resolveReasoningPreview(visibleTimelineText(item.content), { pending: Boolean(item.pending) });
}

/** 折叠态字数胶囊口径，与摘要同源。 */
function reasoningCharCountOf(item: ProcessTimelineTextItem): number {
  return reasoningCharCount(visibleTimelineText(item.content));
}
```

- [ ] **Step 3: 替换折叠行按钮模板**

把 `:82-95` 的整段 `<button v-if="item.textKind === 'reasoning'" ...>...</button>` 替换为：

```vue
                <button
                  v-if="item.textKind === 'reasoning'"
                  type="button"
                  class="mb-0.5 flex w-full items-center gap-2 text-left text-[10px] hover:text-gray-600 dark:hover:text-gray-300"
                  :aria-expanded="isReasoningBodyOpen(item)"
                  @click="item.contentExpanded = isReasoningBodyOpen(item) ? false : true"
                >
                  <CpuChipIcon class="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                  <span class="shrink-0">深度思考</span>
                  <span
                    v-if="reasoningPreviewOf(item).text"
                    class="hidden min-w-0 flex-1 truncate text-gray-400 dark:text-gray-500 sm:block"
                    :title="reasoningPreviewOf(item).truncated ? reasoningPreviewOf(item).text : ''"
                  >{{ reasoningPreviewOf(item).text }}<span v-if="item.pending" class="ml-0.5 animate-pulse">▌</span></span>
                  <span class="ml-auto flex shrink-0 items-center gap-2">
                    <span
                      v-if="reasoningCharCountOf(item) >= REASONING_CHAR_COUNT_MIN_VISIBLE"
                      class="rounded-full bg-gray-100 px-1.5 py-0.5 font-mono text-[10px] text-gray-500 dark:bg-gray-700 dark:text-gray-400"
                      :title="`本次思考共 ${reasoningCharCountOf(item)} 字`"
                    >{{ reasoningCharCountOf(item) }} 字</span>
                    <span v-if="formatDuration(item.execution_time_ms)" class="font-mono text-[10px] text-gray-400">{{ formatDuration(item.execution_time_ms) }}</span>
                    <svg class="h-3 w-3 shrink-0 transition-transform" :class="{ 'rotate-180': isReasoningBodyOpen(item) }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="m19 9-7 7-7-7" />
                    </svg>
                  </span>
                </button>
```

**不要改动**紧随其后的 `<blockquote>`（展开态正文、复制按钮）与 `<pre v-else>` 分支。

- [ ] **Step 4: 类型检查**

```bash
cd /Users/chenxiaolong/workspace/nanzi-ai-agent-platform/frontend
npx vue-tsc --noEmit
```

Expected: 0 报错（与改动前基线一致）。

- [ ] **Step 5: 记录建议提交（由用户执行）**

```bash
git add frontend/src/components/chat/ChatExecutionTimeline.vue
# 建议 commit message：feat(timeline): 折叠态深度思考行展示摘要与字数胶囊
```

---

## Task 3: 追加源码契约断言

**Files:**
- Modify: `tests/frontend/test_model_thinking_config_contract.py`（在 `test_reasoning_panel_uses_model_inference_icon_and_label` 之后追加）

- [ ] **Step 1: 追加契约测试**

在 `tests/frontend/test_model_thinking_config_contract.py` 的 `test_reasoning_panel_uses_model_inference_icon_and_label` 函数之后追加：

```python
def test_collapsed_reasoning_row_shows_preview_and_char_count():
    timeline = (ROOT / "frontend/src/components/chat/ChatExecutionTimeline.vue").read_text(encoding="utf-8")
    assert "resolveReasoningPreview" in timeline
    assert "reasoningCharCount" in timeline
    assert "REASONING_CHAR_COUNT_MIN_VISIBLE" in timeline
    # 阈值必须真的用在渲染条件上，光有 import 不算（防「常量在、判断被删掉」）
    assert 'v-if="reasoningCharCountOf(item) >= REASONING_CHAR_COUNT_MIN_VISIBLE"' in timeline
    # 摘要占中段并截断，窄屏让位（与 Header 的 actionSummary 同策略）
    assert "hidden min-w-0 flex-1 truncate text-gray-400 dark:text-gray-500 sm:block" in timeline
    # 字数胶囊复用 Header 既有胶囊样式，不引入新色系
    assert "rounded-full bg-gray-100 px-1.5 py-0.5 font-mono text-[10px] text-gray-500" in timeline
    # 进行中态尾部光标只挂在折叠行摘要上（展开态那条渲染的是 visibleTimelineText，两者互不冒充）
    assert '>{{ reasoningPreviewOf(item).text }}<span v-if="item.pending" class="ml-0.5 animate-pulse">▌</span></span>' in timeline
    # 截断规则必须留在纯函数模块里，不许被复制进组件
    assert "REASONING_PREVIEW_MAX_CHARS" not in timeline
    module = (ROOT / "frontend/src/utils/reasoningPreview.ts").read_text(encoding="utf-8")
    assert "REASONING_PREVIEW_MAX_CHARS = 80" in module
    assert "REASONING_PREVIEW_MIN_CHARS = 40" in module
    assert "REASONING_CHAR_COUNT_MIN_VISIBLE = 10" in module
```

> **实施中修正（记录两次自检发现的假阳性）**：① 「进行中光标」首版断言的字面量 `<span v-if="item.pending" class="ml-0.5 animate-pulse">▌</span>` 在改动前就已出现 2 次（展开态与旁白），属**假阳性**，改用上方的折叠行特有组合；② 「字数阈值」首版只断言 `"REASONING_CHAR_COUNT_MIN_VISIBLE" in timeline`，**删掉模板里的 `v-if` 后该断言照样通过**（import 语句即满足），收紧为模板 `v-if` 断言后变异 M5 才被捕获。

- [ ] **Step 2: 跑契约测试**

```bash
cd /Users/chenxiaolong/workspace/nanzi-ai-agent-platform
.venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_model_thinking_config_contract.py -q
```

Expected: 全部通过（含既有三条 reasoning 断言未回退）。

- [ ] **Step 3: 记录建议提交（由用户执行）**

```bash
git add tests/frontend/test_model_thinking_config_contract.py
# 建议 commit message：test(timeline): 补折叠态思考摘要与字数胶囊契约断言
```

---

## Task 4: 回归与交付记录

**Files:**
- Modify: `tests/CHECKLIST.md`

- [ ] **Step 1: 跑前端全量测试**

```bash
cd /Users/chenxiaolong/workspace/nanzi-ai-agent-platform
.venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend -q
```

Expected: 0 failed（与改动前基线相比只多出本次新增用例）。

- [ ] **Step 2: 确认后端零改动**

```bash
cd /Users/chenxiaolong/workspace/nanzi-ai-agent-platform
git status --porcelain
```

Expected: 改动只落在 `frontend/src/utils/reasoningPreview.ts`、`frontend/src/components/chat/ChatExecutionTimeline.vue`、`tests/frontend/`、`tests/CHECKLIST.md`、`docs/superpowers/`；无 `app/`、`db-prod*/` 改动。

- [ ] **Step 3: 追加 `tests/CHECKLIST.md` 记录**

在 `tests/CHECKLIST.md` 表格末尾按既有列格式追加一行（列：功能 | 涉及文件 | 说明 | 验证结果 | 日期）：

```
| 会话时间线折叠态「深度思考」摘要与字数（Collapsed Reasoning Preview & Char Count） | `frontend/src/utils/reasoningPreview.ts`, `frontend/src/components/chat/ChatExecutionTimeline.vue`, `tests/frontend/test_reasoning_preview_behavior.py`, `tests/frontend/test_model_thinking_config_contract.py`, `tests/CHECKLIST.md` | **针对用户反馈「折叠后只有深度思考四个字、太单薄」**：① 新增纯函数模块 `reasoningPreview.ts`：Markdown 压平（去标题/列表/引用/围栏/分割线/表格分隔行、链接只留文字、反引号与 `**粗体**` 去标记；**刻意不剥离 `_` 与单个 `*`**，避免改写 `analyze_md_charts.py`、`__init__.py`、`*.md`）、定长 80 字截断并在 40–80 区间回退到最近句读（防半句话）、进行中改为尾部 80 字跟随最新内容并在 12 字窗口内回退到边界、字数口径为压平后去空白的可见字符数；② `ChatExecutionTimeline.vue` 折叠行接入摘要（`truncate` + 窄屏 `hidden sm:block` 让位）、`N 字` 胶囊（复用 Header 既有胶囊样式，不引入新色系）、进行中尾部光标；展开态、复制按钮与折叠语义零变化；③ 测试闭环：新增 14 项纯函数行为测试（Node harness 真跑），补折叠态契约断言，`pytest --confcutdir=tests/frontend tests/frontend` 全绿、`vue-tsc --noEmit` 0 报错；未修改数据库，未代跑服务脚本。 | ✅ 摘要/字数/尾部跟随行为测试 14 项全绿；折叠态契约断言通过；`vue-tsc --noEmit` 0 报错；后端零改动 | 2026-10-14 |
```

- [ ] **Step 4: 记录建议提交（由用户执行）**

```bash
git add tests/CHECKLIST.md docs/superpowers/
# 建议 commit message：docs(timeline): 补折叠态思考摘要交付记录与设计文档
```

- [ ] **Step 5: 通知用户人工验收（Agent 不代跑服务）**

提醒用户在控制台执行 `./dev.sh` 后按 spec §6.4 验收：折叠态摘要与字数、进行中尾部跟随、结束后收在句读、窄屏让位、展开态与复制不受影响。

---

## Self-Review

**Spec coverage：** §4.1/§4.2/§4.3/§4.4/§4.5 → Task 1；§4.6/§4.7 → Task 2；§6.1 → Task 1 Step 1；§6.2 → Task 3；§6.3 → Task 1 Step 5；§6.5 → Task 4 Step 1-2；§8 文件清单 → 各任务 Files 段全部覆盖。§2 非目标（不改展开态、不改数据结构、不改后端）由 Task 2 Step 3 的「不要改动 blockquote」与 Task 4 Step 2 的 `git status` 检查守住。

**Placeholder scan：** 无 TODO/TBD；每个代码步骤都给出完整代码；命令均带预期结果。

**Type consistency：** `ReasoningPreview`（`text` / `charCount` / `truncated`）在 Task 1 定义、Task 2 消费一致；`resolveReasoningPreview` / `reasoningCharCount` / `REASONING_CHAR_COUNT_MIN_VISIBLE` 命名在 spec、Task 1、Task 2、Task 3 四处一致；组件内封装函数名 `reasoningPreviewOf` / `reasoningCharCountOf` 在 Task 2 与 Task 3 的契约断言中未直接引用（断言只锁模块函数名与类名字符串），无漂移风险。
