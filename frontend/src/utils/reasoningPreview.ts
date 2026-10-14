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

/**
 * 剥离行内 Markdown 标记，只留文字。
 *
 * 刻意不处理 `_` 与单个 `*`：思考正文里的 `analyze_md_charts.py`、`__init__.py`、
 * `*.md` 远比 `_斜体_` / `*斜体*` 常见，剥离下划线系标记会把标识符改写掉。
 */
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
