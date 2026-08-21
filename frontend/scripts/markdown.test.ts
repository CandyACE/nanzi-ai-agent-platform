import assert from "node:assert/strict";
import MarkdownIt from "markdown-it";
import { normalizeGroundingNoticeMarkdown } from "../src/utils/markdownNormalization.ts";

const md = new MarkdownIt({ html: true });
const rendered = md.render(normalizeGroundingNoticeMarkdown(
  '<a class="quick-action-btn" href="quick:next">继续分析</a> > **风险提示**：本回答需要结合原始数据核对。',
));

assert.match(rendered, /<blockquote>/, "风险提示应渲染为 Markdown 引用块");
assert.match(rendered, /<strong>风险提示<\/strong>/, "风险提示标题应保留 Markdown 加粗");
assert.doesNotMatch(rendered, /&gt;\s*<strong>风险提示<\/strong>/, "不应把引用符号显示为普通文本");

const alreadySeparated = normalizeGroundingNoticeMarkdown(
  '正文\n\n> **信息来源提示**：请结合原始资料核对。',
);
assert.equal(
  alreadySeparated,
  '正文\n\n> **信息来源提示**：请结合原始资料核对。',
  "已有换行的提示不应被重复插入空行",
);

console.log("markdown.test.ts passed");
