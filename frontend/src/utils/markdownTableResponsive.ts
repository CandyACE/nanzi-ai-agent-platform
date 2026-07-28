export const MOBILE_CARD_COLUMN_THRESHOLD = 4;

const stripHtmlTags = (value: string) =>
  value
    .replace(/<[^>]*>/g, "")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/gi, "'")
    .trim();

const escapeAttribute = (value: string) =>
  value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");

const addTableClass = (tableHtml: string, className: string) => {
  const classPattern = new RegExp(`\\b${className}\\b`);
  if (classPattern.test(tableHtml)) return tableHtml;

  if (/<table\b[^>]*\bclass=["'][^"']*["']/i.test(tableHtml)) {
    return tableHtml.replace(
      /(<table\b[^>]*\bclass=["'])([^"']*)(["'])/i,
      (_match, prefix, classes, suffix) => `${prefix}${classes} ${className}${suffix}`,
    );
  }

  return tableHtml.replace(/<table\b/i, `<table class="${className}"`);
};

const addCellLabels = (tableHtml: string, headers: string[]) =>
  tableHtml.replace(/(<tbody\b[^>]*>[\s\S]*?<\/tbody>)/i, (tbody) =>
    tbody.replace(/<tr\b[^>]*>[\s\S]*?<\/tr>/gi, (row) => {
      let cellIndex = 0;
      return row.replace(/<td\b([^>]*)>([\s\S]*?)<\/td>/gi, (cell, attrs, inner) => {
        const currentIndex = cellIndex;
        cellIndex += 1;
        if (/\bdata-label\s*=/i.test(attrs)) return cell;
        const label = headers[currentIndex] || `第 ${currentIndex + 1} 列`;
        return `<td${attrs} data-label="${escapeAttribute(label)}">${inner}</td>`;
      });
    }),
  );

export const enhanceMarkdownTablesForMobile = (tableHtml: string): string => {
  const hasDataCells = /<tbody\b[^>]*>[\s\S]*?<td\b/i.test(tableHtml);
  if (
    !/<thead\b/i.test(tableHtml)
    || !hasDataCells
    || /\b(?:colspan|rowspan)\b/i.test(tableHtml)
  ) {
    return addTableClass(tableHtml, "markdown-table-mobile-compact");
  }

  const headers = [...tableHtml.matchAll(/<th\b[^>]*>([\s\S]*?)<\/th>/gi)]
    .map((match) => stripHtmlTags(match[1] || ""));

  if (headers.length < MOBILE_CARD_COLUMN_THRESHOLD) {
    return addTableClass(tableHtml, "markdown-table-mobile-compact");
  }

  return addTableClass(
    addCellLabels(tableHtml, headers),
    "markdown-table-mobile-cards",
  );
};
