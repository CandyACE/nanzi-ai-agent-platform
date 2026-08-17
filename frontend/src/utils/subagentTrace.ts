export interface SubagentTraceMeta {
  display_name?: string | null
  agent_name?: string | null
  run_id?: string | null
  parent_trace_id?: string | null
  child_trace_id?: string | null
  stop_reason?: string | null
  tool_filter?: string[] | null
}

const asNonEmptyString = (value: unknown): string | null => {
  if (typeof value !== 'string') return null
  const normalized = value.trim()
  return normalized || null
}

export const normalizeSubagentTraceMeta = (value: unknown): SubagentTraceMeta | undefined => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return undefined
  const source = value as Record<string, unknown>
  const toolFilter = Array.isArray(source.tool_filter)
    ? source.tool_filter.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
    : null
  const normalized: SubagentTraceMeta = {
    display_name: asNonEmptyString(source.display_name),
    agent_name: asNonEmptyString(source.agent_name),
    run_id: asNonEmptyString(source.run_id),
    parent_trace_id: asNonEmptyString(source.parent_trace_id),
    child_trace_id: asNonEmptyString(source.child_trace_id),
    stop_reason: asNonEmptyString(source.stop_reason),
    tool_filter: toolFilter,
  }
  return Object.values(normalized).some((item) => item !== null && item !== undefined)
    ? normalized
    : undefined
}

export const subagentDisplayName = (meta?: SubagentTraceMeta): string =>
  meta?.display_name || meta?.agent_name || '子代理'

export const formatSubagentTraceSummary = (meta?: SubagentTraceMeta): string => {
  if (!meta) return ''
  const label = subagentDisplayName(meta)
  const tools = meta.tool_filter?.length ? ` · 工具：${meta.tool_filter.join('、')}` : ''
  const stopReason = meta.stop_reason ? ` · ${meta.stop_reason}` : ''
  return `${label}${tools}${stopReason}`
}

