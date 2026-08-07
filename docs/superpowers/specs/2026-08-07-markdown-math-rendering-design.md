# Markdown 数学公式渲染设计

## 目标

让普通 AI 消息和画布 Markdown 统一支持 LaTeX 数学公式，至少覆盖块级公式 `$$...$$`、行内公式 `$...$`，并兼容示例中的 `\\text{（个）}`。

## 范围

- `MessageRenderer` 使用的普通消息、EmbedChat、AgentDebug 和历史消息渲染。
- `CanvasMarkdownRenderer` 使用的画布 Markdown 预览。
- 代码块中的美元符号和 LaTeX 文本保持代码原样，不触发公式解析。
- 公式解析失败时保留原始 Markdown，不让整条消息渲染失败。

## 方案

在现有 `frontend/src/utils/markdown.ts` 中统一接入 `markdown-it-texmath` 和 KaTeX：

1. `renderMarkdown` 与 `renderMarkdownPreview` 共用同一个公式插件配置。
2. 使用 KaTeX 输出 HTML，并由共享渲染层引入 KaTeX 样式。
3. 继续保留现有代码高亮、表格、链接和 Mermaid/图表分段逻辑。
4. 公式插件只处理 Markdown 正文，不处理 fenced code token。

## 降级与安全

- KaTeX `throwOnError` 关闭，未知命令以可见原文显示，避免阻断消息。
- 继续沿用现有 `v-html` 渲染边界和 Markdown 链接处理规则。
- 不改变后端消息格式，公式以现有 Markdown 文本传输。

## 验证

- 渲染契约验证 `$$3 + 5 = 8 \\text{（个）}$$` 进入 KaTeX 输出。
- 验证行内公式、代码块保护、普通消息渲染器和画布预览均使用统一配置。
- 运行前端契约测试、`vue-tsc --noEmit` 和 `git diff --check`。
