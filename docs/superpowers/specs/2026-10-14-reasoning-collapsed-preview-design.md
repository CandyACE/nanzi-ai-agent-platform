# 折叠态「深度思考」摘要与字数设计

## 1. 问题背景

用户在会话执行时间线的截图中指出：折叠状态的「深度思考」行只有 `CpuChip 图标 + 深度思考 + 耗时` 四个字，是整条时间线里信息量最低的一行；展开后才看得到完整思考内容。

对照之下，同一列表里的工具行已经有「标题 + 摘要」的密度：

```
⟳ 工具完成 · Write · 写入文件          10.6s  ⌄
    路径：/workspace/sessions/.../analyze_md_charts.py
🧠 深度思考                             1.4s  ⌄   ← 零信息量
✦ 模型调用 · DeepSeek-V4-Pro            1.0s  ⌄
```

### 现状代码

`frontend/src/components/chat/ChatExecutionTimeline.vue:82-95` 的折叠行按钮只渲染图标、`深度思考` 字面量、`formatDuration(item.execution_time_ms)` 与折叠箭头；正文在 `:96-117` 的 `<blockquote>` 里，由 `item.contentExpanded` 控制显示（`isReasoningBodyOpen` → `isReasoningContentExpanded`，`processTimeline.ts:685-689`：未显式设置时「进行中展开、结束后折叠」）。

`item.content` 是完整思考正文（SSE `reasoning_content` 增量累积，`processTimeline.ts:651-668`），也就是**折叠态其实一直握着全文，只是没用**。

### 展示口径的选型过程

用可视化 mockup 对比了五档（每档都放在同一条真实时间线上下文里渲染）：

| 档位 | 做法 | 结论 |
| --- | --- | --- |
| A 现状 | 仅标题 + 耗时 | 用户指出信息量为零，否决 |
| B 首句优先 | 摘到第一个句号即停 | 右侧常留大片空白（首句往往很短），未选 |
| C 两行预览 | 标题行 + 正文前两行 `line-clamp-2` | 信息最足，但每块高约 40px，长任务时间线显著变长，未选 |
| D 尾句结论 | 显示最后一句（结论） | 流式中尾句不断跳动、中途常为半句，未选 |
| E 固定长度 + 字数胶囊（**选用**） | 标题 + 定长摘要（回退句读）+ `N 字` 胶囊 | 高度不变、密度稳定，用户确认 |

同时确认了两项配套行为：进行中态摘要**尾部跟随**（用户已认可 C 屏），窄屏摘要**自动让位**（与 Header 的 `actionSummary` 同策略）。

## 2. 目标与非目标

### 目标

- 折叠态思考行显示正文摘要，长度上限固定、落在句读边界上，不出现半句话；
- 折叠态显示该次思考的可见字符数（`268 字`），与摘要同源；
- 进行中的思考行摘要跟随最新吐出的内容（尾部 80 字），并有明确的进行中指示；
- 摘要规则抽成纯函数，可用仓库既有 Node harness 直接单测；
- 展开态、复制、点击折叠、`isReasoningContentExpanded` 的既有语义**零变化**。

### 非目标

- **不改展开态**：正文仍是 `<pre>` 里原样 Markdown，不重排、不渲染 Markdown；
- **不做模型侧摘要**：不调用大模型生成摘要、不新增 SSE 字段、不改 `reasoning_content` 的落库与传输；
- **不改数据结构**：`ProcessTimelineTextItem` 不新增持久字段（摘要纯派生）；
- **不改工具行、Header、单卡秒表、挂起安抚文案**；
- **不调整思考行字号**：摘要沿用该行既有的 `text-[10px]`（该行标题本就是 10px），字号统一提及与否留待后续单独评估。

## 3. 方案选择

| 方案 | 做法 | 结论 |
| --- | --- | --- |
| **1（选用）** | 新建 `frontend/src/utils/reasoningPreview.ts` 纯函数模块，组件模板接入 | 摘要可单测、职责单一；`processTimeline.ts` 已 1354 行，不再塞入 |
| 2 | 摘要逻辑写成组件内 computed | 无法单测（组件模板断言只能做字面量契约），且组件继续膨胀（已 1242 行） |
| 3 | 后端下发摘要字段 | 需要改 SSE 协议与存储、为纯展示派生数据付出链路成本，且历史会话无该字段 |
| 4 | 抽出 `TimelineReasoningRow.vue` 子组件 | 能一次算完摘要，但会把 `深度思考`/`textKind === 'reasoning'` 等既有契约字面量搬离 `ChatExecutionTimeline.vue`（既有测试断言锁定在该文件），为本次收益不值当 |

取方案 1。

## 4. 详细设计

### 4.1 纯函数模块 `reasoningPreview.ts`

```ts
/** 摘要正文字符上限。 */
export const REASONING_PREVIEW_MAX_CHARS = 80;
/** 允许回退到句读的最小长度：短于此长度宁可硬截，也不摘出半行。 */
export const REASONING_PREVIEW_MIN_CHARS = 40;
/** 低于该字数不显示「N 字」胶囊，避免开流瞬间闪一个「1 字」。 */
export const REASONING_CHAR_COUNT_MIN_VISIBLE = 10;

export interface ReasoningPreview {
  /** 折叠态展示文本；无可展示内容时为空串。 */
  text: string;
  /** 压平后的可见字符数（已去空白与 Markdown 标记）。 */
  charCount: number;
  /** 摘要是否被截断（决定是否加省略号、是否值得给 title）。 */
  truncated: boolean;
}

/** 压平 Markdown：去标记、折叠空白，得到一行可读纯文本。 */
export function flattenReasoningText(raw: string): string;

/** 可见字符数（压平后去掉全部空白）。 */
export function reasoningCharCount(raw: string): number;

/** 折叠态摘要：pending 时取尾部（跟随最新内容），否则取头部并回退句读。 */
export function resolveReasoningPreview(
  raw: string,
  options?: { pending?: boolean },
): ReasoningPreview;
```

### 4.2 Markdown 压平规则

按行处理，再合并行内标记，最后折叠空白：

| 输入形态 | 处理 | 例 |
| --- | --- | --- |
| `# 标题` / `### 分析步骤`（`^\s{0,3}#{1,6}\s+`） | 去掉井号与空格 | `分析步骤` |
| `- 条目` / `* 条目` / `+ 条目` | 去掉符号与空格 | `条目` |
| `1. 条目` / `1) 条目` | 去掉序号与空格 | `条目` |
| `> 引用` | 去掉尖括号与空格 | `引用` |
| ` ``` ` / ` ```python ` 围栏行 | 整行丢弃（围栏内的文本**保留**） | — |
| `---` / `***` / `___` 分割线 | 整行丢弃 | — |
| `` `code` `` | 去反引号留文字 | `code` |
| `**粗**` | 去标记留文字 | `粗` |
| `[文字](url)` / `![替代](url)` | 只留文字 | `文字` |
| 表格 `\| a \| b \|` | 竖线替换为空格 | `a b` |
| 表格分隔行 `\| --- \| --- \|` | 整行丢弃（`^\|\s*:?-{3,}` 形态） | — |
| 换行、连续空格、制表符 | 折叠为单个空格，首尾 trim | — |

**刻意不剥离 `_` 与单个 `*`**：思考正文里的 `analyze_md_charts.py`、`__init__.py`、`*.md` 远比 Markdown 的 `_斜体_` / `*斜体*` 常见，剥离下划线系标记会把标识符改写成 `analyzemdcharts.py`、`init.py`——这是比摘要里留两个标记符号严重得多的错误。`**粗体**` 保留剥离（`**` 在正文中几乎只用于 Markdown，误伤面仅是 `**kwargs` 这类语法，影响限于丢掉标记符号本身）。

**不做 HTML 实体解码**：思考正文里的 `&lt;` 之类原样保留字符，避免引入解码歧义（有需要时在后续单独处理）。

### 4.3 截断与句读回退（已完成态）

设 `flat` 为压平结果：

1. `flat.length <= 80` → 摘要即全文，`truncated = false`，不加省略号；
2. 否则在 `flat.slice(0, 80)` 内，从第 80 位向前找 `[40, 80]` 区间中**最后一个**句读字符（`。！？；!?;`）：
   - 命中 → 切在该字符**之后**（保留句读），`truncated = true`；
   - 未命中 → 硬截 80 字符，`truncated = true`；
3. 截断时末尾追加 `…`。

`REASONING_PREVIEW_MIN_CHARS = 40` 这个下界防的是「首句极短时摘要只剩半行、右侧空一片」——这正是 mockup 里方案 B 被否掉的观感。40 字以内的句读点一律不认，宁可写满到 80。

### 4.4 尾部跟随（进行中态）

`options.pending === true` 时取**尾部**：

1. `flat.length <= 80` → 同 4.3 第 1 条（不加前缀）；
2. 否则取 `flat.slice(-80)`，再在**开头 12 个字符内**寻找第一个空白或标点（`\s，。；！？、,;!?`），从其后开始（避免从半个词／半个数字中间切入；中文场景下多数时候直接命中标点）；
3. 前缀 `…`，`truncated = true`。

尾部跟随同时覆盖了「才刚开始思考、内容不足 80 字」与「已想了几千字」两种情况，且不需要额外状态。

### 4.5 字数口径

`charCount = flattenReasoningText(raw).replace(/\s/g, "").length`，即**压平后的可见字符数**（中英文均按字符计，标点计入）。与摘要是同一份文本，所以「268 字」描述的正是用户能在展开态看到的那段内容的体量。

组件侧：`charCount < REASONING_CHAR_COUNT_MIN_VISIBLE` 时不渲染胶囊。

### 4.6 组件接入 `ChatExecutionTimeline.vue`

折叠行按钮（`:82-95`）改为：

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
  >
    {{ reasoningPreviewOf(item).text }}<span v-if="item.pending" class="ml-0.5 animate-pulse">▌</span>
  </span>
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

组件脚本侧新增导入与三个薄封装（`visibleTimelineText` 保持唯一入口，内部上下文块剥离不重复实现）：

```ts
import {
  REASONING_CHAR_COUNT_MIN_VISIBLE,
  reasoningCharCount,
  resolveReasoningPreview,
  type ReasoningPreview,
} from "@/utils/reasoningPreview";

function reasoningPreviewOf(item: ProcessTimelineTextItem): ReasoningPreview {
  return resolveReasoningPreview(visibleTimelineText(item.content), { pending: Boolean(item.pending) });
}

function reasoningCharCountOf(item: ProcessTimelineTextItem): number {
  return reasoningCharCount(visibleTimelineText(item.content));
}
```

要点：

- **颜色沿用行内既有灰阶**：摘要 `text-gray-400 dark:text-gray-500`（比标题浅一档，与工具行的路径摘要同层级）；进行中时外层容器已是 `text-gray-600 dark:text-gray-300`，摘要颜色不变，靠左侧呼吸点与尾部光标表达「正在思考」。
- **胶囊复用 Header 既有样式**：`rounded-full bg-gray-100 px-1.5 py-0.5 font-mono text-[10px] text-gray-500`（`ChatThinkingHeader.vue:40-42`），不引入新色系、不引入紫色。
- **`shrink-0` + `flex-1` + `ml-auto`**：摘要占满中段并 `truncate`；窄屏摘要 `display:none` 时右组靠 `ml-auto` 顶到行尾。
- **尾部光标与展开态一致**：`▌ animate-pulse`（复用 `:116` 的既有写法）。
- **`title` 只在截断时给**：没截断时摘要即全文，再挂 tooltip 是噪声。
- **模板内多次调用是刻意的**：`reasoningPreviewOf(item)` 在一次渲染里会被求值 2–3 次。单次成本是几次正则 `replace`（微秒级），时间线中思考行数量有限，不值得为此引入缓存或子组件（YAGNI）；若将来实测有压力，再在组件内加 `WeakMap` 按 `item` 缓存。

### 4.7 数据流

```
SSE reasoning_content 增量
        │
        ▼
processTimeline.appendTimelineReasoningDelta → item.content 累积（pending: true）
        │
        ▼
ChatExecutionTimeline 渲染折叠行
        │
        ├─ blockquote（展开态，未改动）── item.content 原样
        │
        └─ 折叠行
             visibleTimelineText(item.content)   剥离内部上下文块（既有函数）
                     │
                     ▼
             resolveReasoningPreview(raw, { pending })
                     │
                     ├─ flattenReasoningText → 压平 Markdown
                     ├─ pending ? 尾部 80 字 : 头部 80 字（回退句读）
                     └─ charCount（同源文本去空白）
                     │
                     ▼
             摘要文本（truncate）+ 「N 字」胶囊 + 耗时 + 折叠箭头
```

## 5. 边界与已知限制

| 场景 | 行为 |
| --- | --- |
| 正文短于 80 字 | 摘要即全文、无省略号、无 tooltip |
| 正文只有 Markdown 符号（如全是 `---`） | 压平后为空串 → 折叠行只显示「深度思考 + 耗时」，与现状一致 |
| 正文为空（刚收到 pending 但还没内容） | 同上一行：不渲染摘要与胶囊，不出现空占位 |
| 正文短于 10 字 | 摘要照常显示，但不显示「N 字」胶囊（防开流瞬间闪烁） |
| 内容含代码块 | 围栏行被丢弃，围栏内文本按普通文字参与摘要（不做代码识别） |
| 英文／数字正文 | 尾部跟随会在开头 12 字符内回退到空白或标点，避免半个单词；极端情况下（前 12 字符无空白的英文长词）仍可能切断 |
| emoji／组合字符 | 按 UTF-16 码元计数（`String.length`），一个字素簇可能计为 2；仅影响字数胶囊的显示值，不影响截断安全（`slice` 不产生非法串） |
| 并行子代理（`sourceLabel`） | 各 `reasoning` 条目独立成行，摘要与字数各自计算，互不影响 |
| 同一轮多个思考块 | 每块独立展示自己的摘要与字数（时间线本就按块分行） |
| 展开/折叠切换 | 摘要始终按同一规则计算，切换不改变其内容与位置 |
| 「全部展开明细」 | `toggleAllDetails` 只改 `contentExpanded`，不影响摘要 |
| 历史会话（无流式） | 摘要由 `item.content` 现场派生，历史加载与实时流一致；不做落库字段，无迁移 |

## 6. 测试策略

### 6.1 行为测试（Node 真跑，新增 `tests/frontend/test_reasoning_preview_behavior.py`）

复用仓库既有 `_run_typescript` harness（`node` + `frontend/node_modules/typescript` 的 `transpileModule`），`MODULE = "frontend/src/utils/reasoningPreview.ts"`：

| 输入 | 期望 |
| --- | --- |
| `flattenReasoningText("### 分析步骤\n- 先看目录\n- 再确认命名")` | `"分析步骤 先看目录 再确认命名"` |
| 含 ` ``` ` 围栏 + 围栏内文本 | 围栏行消失、内部文本保留 |
| 含 `**要点**`、`` `code` ``、`[官方文档](https://example.com)` | `要点`、`code`、`官方文档`（标记与 URL 消失） |
| `"跑 analyze_md_charts.py 与 __init__.py"` | **原样不变**（`_` 系标记不剥离，锁住标识符不被改写） |
| 含表格分隔行 `\| --- \| --- \|` | 该行消失；表头与内容行保留 |
| 120 字且第 60 字处有 `。` | 摘要在该句号后结束，`truncated === true` |
| 120 字且全篇无句读 | 摘要长度 80（+省略号），`truncated === true` |
| 120 字且首个句读在第 20 字处 | **不在 20 字处回退**（低于 40 下界），继续找 40–80 区间；未命中则写满 80 字 |
| 120 字、句读落在距尾部 75 字处，`pending: true` | 摘要取自**结尾**、以 `…` 开头，并在尾部窗口内回退到该句读**之后** |
| `pending: true` 且 30 字 | 摘要即全文，**无** `…` 前缀 |
| 空串 / 纯空白 / 纯 Markdown 符号 | `text === ""`、`charCount === 0`、`truncated === false` |
| `reasoningCharCount("**你好** 世界")` | `4`（标记与空白都不计） |
| 三个导出常量 | `80` / `40` / `10` |

### 6.2 源码契约（追加到既有 thinking 契约测试）

- `ChatExecutionTimeline.vue` 含 `resolveReasoningPreview`、`reasoningCharCount`、`REASONING_CHAR_COUNT_MIN_VISIBLE`；
- 折叠行摘要带 `truncate` 与 `hidden ... sm:block`（锁「窄屏让位」）；
- 胶囊样式字符串 `rounded-full bg-gray-100 px-1.5 py-0.5 font-mono text-[10px] text-gray-500` 出现在思考行内（锁复用 Header 胶囊，防新色系混入）；
- 既有三条断言（`深度思考`、`item.textKind === 'reasoning'`、无 `🧠` emoji）**保持不变**——本次不搬移这些字面量。

### 6.3 变异验证

1. 去掉 `REASONING_PREVIEW_MIN_CHARS` 下界（任何句读都回退）→ 应被「首句读在 20 字处」用例捕获；
2. 把尾部跟随改回头部 → 应被 `pending` 用例捕获；
3. 摘要上限改 200 → 应被「长度 80」用例捕获；
4. 字数为 `flat.length`（含空格）→ 应被 `"**你好** 世界" → 4` 捕获；
5. 压平漏掉标题井号 → 应被第一条 `flattenReasoningText` 用例捕获；
6. 窄屏断点去掉（`hidden sm:block` 改常显）→ 应被契约断言捕获；
7. 给压平规则补上 `_([^_]+)_` 下划线斜体剥离 → 应被 `analyze_md_charts.py / __init__.py` 用例捕获；
8. 尾部跟随去掉窗口内边界回退（直接切 80 字）→ 应被「句读落在距尾部 75 字处」用例捕获。

### 6.4 人工验证（跑 `./dev.sh` 后）

1. 提一个需要长思考的问题：折叠态思考行能看到逐字增长的摘要与实时字数，进行中尾部跟随；
2. 思考结束后摘要停在句读边界、不出现半句话；
3. 点开思考行能看到完整正文，复制按钮仍可用；
4. 手机宽度（≤ 640px）下摘要让位，只留「深度思考 + N 字 + 耗时」。

### 6.5 回归

- `pytest --confcutdir=tests/frontend tests/frontend` 全量 0 failed（含既有 thinking 契约与时间线行为测试）；
- `vue-tsc --noEmit` 0 报错；
- 本次**纯前端改动**，后端文件零改动，无数据库变更。

## 7. 兼容性与回滚

- 无表结构变更、无迁移、无新增依赖、无 SSE 协议变更、无后端改动；
- 摘要与字数均由 `item.content` 现场派生，历史会话与实时流行为一致；
- 回滚：删除 `reasoningPreview.ts` 与新增测试，还原 `ChatExecutionTimeline.vue` 的折叠行按钮与三行辅助函数即可，无数据残留。

## 8. 涉及文件清单

| 文件 | 变更 |
| --- | --- |
| `frontend/src/utils/reasoningPreview.ts`（新增） | 摘要压平 / 截断 / 尾部跟随 / 字数口径的纯函数模块 |
| `frontend/src/components/chat/ChatExecutionTimeline.vue` | 折叠行按钮接入摘要、字数胶囊与窄屏让位；新增三个薄封装函数 |
| `tests/frontend/test_reasoning_preview_behavior.py`（新增） | 纯函数行为测试（Node harness） |
| `tests/frontend/test_model_thinking_config_contract.py` | 追加折叠态摘要与胶囊的源码契约断言 |
| `tests/CHECKLIST.md` | 新增本次交付记录 |
