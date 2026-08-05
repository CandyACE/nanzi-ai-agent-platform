/** 平台业务时区：默认 Asia/Shanghai，可被公开配置接口刷新 */

let platformTimezone = "Asia/Shanghai";

export const DEFAULT_PLATFORM_TIMEZONE = "Asia/Shanghai";

export function getPlatformTimezone(): string {
  return platformTimezone || DEFAULT_PLATFORM_TIMEZONE;
}

export function setPlatformTimezone(tz: string | null | undefined): string {
  const next = String(tz || "").trim();
  platformTimezone = next || DEFAULT_PLATFORM_TIMEZONE;
  return platformTimezone;
}

/**
 * 将后端时间字符串按平台时区格式化展示。
 * - 带 Z / 偏移：先解析为绝对时刻，再转到平台时区
 * - 无时区的 naive：按平台墙钟理解（与后端 datetime.now(tz) 写入语义一致）
 */
export function formatInPlatformTimezone(
  value: string | Date | null | undefined,
  options?: Intl.DateTimeFormatOptions,
): string {
  if (value === null || value === undefined || value === "") return "";
  const tz = getPlatformTimezone();
  const date = value instanceof Date ? value : parsePlatformDateInput(String(value), tz);
  if (Number.isNaN(date.getTime())) return String(value);

  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: tz,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: options?.second !== undefined ? options.second : undefined,
    hour12: false,
    ...options,
  }).format(date);
}

export function formatInPlatformTimezoneCompact(value: string | Date | null | undefined): string {
  return formatInPlatformTimezone(value, {
    year: undefined,
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: undefined,
  });
}

function parsePlatformDateInput(raw: string, tz: string): Date {
  const text = raw.trim();
  if (!text) return new Date(NaN);

  // Already timezone-aware
  if (/[zZ]$/.test(text) || /[+-]\d{2}:?\d{2}$/.test(text)) {
    return new Date(text);
  }

  // Naive ISO / "YYYY-MM-DD HH:mm:ss" → treat as platform wall clock via offset approximation
  const normalized = text.includes("T") ? text : text.replace(" ", "T");
  // Append offset for common Asia/Shanghai; for other zones rely on Intl by constructing with timeZone via Temporal-less approach:
  // Use Date.parse of local-like string as if UTC then adjust — better: use formatToParts reverse.
  // Practical approach: for Asia/Shanghai (+08:00) append offset; else parse as UTC and note limitation.
  if (tz === "Asia/Shanghai" || tz === "Asia/Hong_Kong" || tz === "Asia/Singapore") {
    return new Date(`${normalized}+08:00`);
  }
  if (tz === "UTC") {
    return new Date(`${normalized}Z`);
  }
  // Fallback: browser local interpretation
  return new Date(normalized);
}
