import { downloadMarkdownFile } from "@/utils/chatSessionExport";

function escapeMarkdownCell(value: unknown): string {
  if (value === null || value === undefined) return "";
  let text: string;
  if (typeof value === "object") {
    try {
      text = JSON.stringify(value);
    } catch {
      text = String(value);
    }
  } else {
    text = String(value);
  }
  return text.replace(/\r?\n/g, " ").replace(/\|/g, "\\|").trim();
}

export function buildChatBIResultMarkdown(options: {
  columns: string[];
  rows: unknown[][];
  totalRowCount?: number;
  resultId?: string | null;
  sampleNotice?: string;
}): string {
  const columns = options.columns || [];
  const rows = options.rows || [];
  const total = Number(options.totalRowCount || rows.length || 0);
  const exportedAt = new Date().toLocaleString("zh-CN");
  const lines: string[] = [
    "# ChatBI 查询结果明细",
    "",
    `- **导出时间:** ${exportedAt}`,
    `- **总行数:** ${total}`,
    `- **导出行数:** ${rows.length}`,
  ];
  if (options.resultId) {
    lines.push(`- **结果 ID:** \`${options.resultId}\``);
  }
  if (options.sampleNotice) {
    lines.push(`- **说明:** ${options.sampleNotice}`);
  }
  lines.push("", "---", "");

  if (!columns.length) {
    lines.push("_(无列)_", "");
    return lines.join("\n");
  }

  lines.push(`| ${columns.map(escapeMarkdownCell).join(" | ")} |`);
  lines.push(`| ${columns.map(() => "---").join(" | ")} |`);
  for (const row of rows) {
    const cells = columns.map((_, index) => escapeMarkdownCell(row?.[index]));
    lines.push(`| ${cells.join(" | ")} |`);
  }
  lines.push("");
  return lines.join("\n");
}

export function exportChatBIResultMarkdown(options: {
  columns: string[];
  rows: unknown[][];
  totalRowCount?: number;
  resultId?: string | null;
  sampleNotice?: string;
}): void {
  const content = buildChatBIResultMarkdown(options);
  const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, (ch) => (ch === "T" ? "_" : "-"));
  const prefix = options.resultId ? String(options.resultId).slice(0, 8) : "result";
  downloadMarkdownFile(`chatbi_result_${prefix}_${stamp}.md`, content);
}
