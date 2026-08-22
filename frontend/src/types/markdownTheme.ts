export const MARKDOWN_THEMES = [
  "default",
  "minimal",
  "academic",
  "apple",
  "warm",
  "compact",
  "bauhaus",
  "editorial",
  "zen",
] as const;

export type MarkdownTheme = (typeof MARKDOWN_THEMES)[number];

export function normalizeMarkdownTheme(value: unknown): MarkdownTheme {
  return typeof value === "string" && (MARKDOWN_THEMES as readonly string[]).includes(value)
    ? (value as MarkdownTheme)
    : "default";
}
