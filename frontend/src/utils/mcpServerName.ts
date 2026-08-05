export type McpServerScope = 'global' | 'personal'

const normalizeNamePart = (value: unknown, fallback: string) => {
  const normalized = String(value || '')
    .trim()
    .replace(/[^a-zA-Z0-9_-]+/g, '-')
    .replace(/^-+|-+$/g, '')

  return normalized || fallback
}

/** 固定前缀，含尾部 `-`，例如 mcp-private-admin- / mcp-public-admin- */
export const buildMcpServerNamePrefix = (
  scope: McpServerScope,
  username: unknown,
) => {
  const userPart = normalizeNamePart(username, 'user')
  if (scope === 'personal') {
    return `mcp-private-${userPart}-`
  }
  return `mcp-public-${userPart}-`
}

export const normalizeMcpServerNameSuffix = (value: unknown) =>
  normalizeNamePart(value, '')

export const composeMcpServerName = (
  scope: McpServerScope,
  username: unknown,
  suffix: unknown,
) => {
  const prefix = buildMcpServerNamePrefix(scope, username)
  const normalizedSuffix = normalizeMcpServerNameSuffix(suffix)
  if (!normalizedSuffix) return ''
  return `${prefix}${normalizedSuffix}`
}

/** 编辑时从完整名剥离当前用户前缀；无法匹配则返回原文以便用户改后缀 */
export const stripMcpServerNamePrefix = (
  fullName: unknown,
  scope: McpServerScope,
  username: unknown,
) => {
  const name = String(fullName || '').trim()
  if (!name) return ''
  const prefix = buildMcpServerNamePrefix(scope, username)
  if (name.toLowerCase().startsWith(prefix.toLowerCase())) {
    return name.slice(prefix.length)
  }
  // 兼容历史：mcp-public-{suffix}（无用户名）
  if (scope === 'global' && /^mcp-public-/i.test(name)) {
    return name.replace(/^mcp-public-/i, '')
  }
  if (scope === 'personal' && /^mcp-private-[^-]+-/i.test(name)) {
    return name.replace(/^mcp-private-[^-]+-/i, '')
  }
  return name
}

/** @deprecated 优先用 composeMcpServerName；保留给旧调用方 */
export const buildDefaultMcpServerName = (
  scope: McpServerScope,
  username: unknown,
  mcpName: unknown,
) => composeMcpServerName(scope, username, mcpName) || buildMcpServerNamePrefix(scope, username) + 'server'
