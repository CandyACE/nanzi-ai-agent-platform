const GROUNDING_NOTICE_PATTERN =
  /(^|[^\n])[ \t]*>([ \t]*\*\*(?:风险提示|信息来源提示)\*\*)/g;

/**
 * 保证事实来源风险提示从新段落开始，避免被前一段 HTML/SSE 文本拼成普通字符。
 * 仅处理平台生成的两类固定提示，不改变用户正文中的其他 Markdown 引用。
 */
export const normalizeGroundingNoticeMarkdown = (content: string): string => {
  if (!content) return '';

  return content.replace(
    GROUNDING_NOTICE_PATTERN,
    (match, prefix: string, title: string) => {
      if (!prefix) return match;
      return `${prefix.trimEnd()}\n\n> ${title.trimStart()}`;
    },
  );
};
