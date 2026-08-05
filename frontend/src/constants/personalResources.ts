import type { WorkbenchPersonalResource } from "@/types/workbench"

/** 与 app/services/workbench_home_service.py PERSONAL_RESOURCE_DEFS 对齐 */
export const PERSONAL_RESOURCE_DEFS = [
  { key: "memory", label: "我的记忆", unit: "条", tab: "memory" },
  { key: "tokens", label: "我的 Token", unit: "本月", tab: "tokens" },
  { key: "data", label: "我的数据门户", unit: "份报表", tab: "data" },
  { key: "skills", label: "我的技能", unit: "个", tab: "skills" },
  { key: "mcp", label: "我的 MCP", unit: "个服务", tab: "mcp" },
  { key: "tasks", label: "我的任务", unit: "个", tab: "tasks" },
] as const

export type PersonalResourceTab = (typeof PERSONAL_RESOURCE_DEFS)[number]["tab"]

/** home 尚未返回：静默占位，避免误显示「暂时无法获取」 */
export function personalResourcePlaceholderItems(): WorkbenchPersonalResource[] {
  return PERSONAL_RESOURCE_DEFS.map((spec) => ({
    key: spec.key,
    label: spec.label,
    value: 0,
    unit: spec.unit,
    tab: spec.tab,
    status: "empty" as const,
  }))
}

/** home 请求失败：显示 -- / 暂时无法获取 */
export function personalResourceFallbackItems(): WorkbenchPersonalResource[] {
  return PERSONAL_RESOURCE_DEFS.map((spec) => ({
    key: spec.key,
    label: spec.label,
    value: 0,
    unit: spec.unit,
    tab: spec.tab,
    status: "error" as const,
  }))
}
