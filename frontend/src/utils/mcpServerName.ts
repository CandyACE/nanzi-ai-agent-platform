export type McpServerScope = 'global' | 'personal'

const normalizeNamePart = (value: unknown, fallback: string) => {
  const normalized = String(value || '')
    .trim()
    .replace(/[^a-zA-Z0-9_-]+/g, '-')
    .replace(/^-+|-+$/g, '')

  return normalized || fallback
}

export const buildDefaultMcpServerName = (
  scope: McpServerScope,
  username: unknown,
  mcpName: unknown,
) => {
  const normalizedMcpName = normalizeNamePart(mcpName, 'server')
  if (scope === 'personal') {
    return `mcp-private-${normalizeNamePart(username, 'user')}-${normalizedMcpName}`
  }
  return `mcp-public-${normalizedMcpName}`
}
