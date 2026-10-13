/**
 * 「禁用工具与命令」候选分组纯函数（spec §3.4）。
 *
 * 设计取舍：候选的归属与展示标签（`group_key` / `group`）由后端决定，
 * 前端**只按 `group_key` 聚合、直接渲染 `group`**，不在这里做任何类别中文映射
 * —— 否则又会出现一份与后端平行的硬编码（v1 已吃过三份硬编码漂移的亏）。
 */

export interface ForbiddenToolCandidate {
  id: string
  label: string
  description: string
  category: string
  aliases: string[]
  /** 稳定聚合键：`builtin:<category>` / `api:<group_name|__ungrouped__>` / `mcp:<server_name|__unknown__>`。 */
  group_key: string
  /** 展示标题，前端直接渲染。 */
  group: string
}

export interface ForbiddenToolSubGroup {
  key: string
  label: string
  candidates: ForbiddenToolCandidate[]
}

/** 缺少 `group_key` 时的兜底聚合键（后端应始终给值，这里是防御而不是契约）。 */
const UNGROUPED_KEY = '__ungrouped__'

/**
 * 按 `group_key` 聚合且保序：子组顺序 = 候选首次出现顺序，组内候选顺序同样保持。
 * 不会产生空组；`group_key` 缺失的候选归入兜底组。
 */
export function groupCandidates(candidates: ForbiddenToolCandidate[]): ForbiddenToolSubGroup[] {
  const groups = new Map<string, ForbiddenToolSubGroup>()
  ;(candidates || []).forEach((candidate) => {
    if (!candidate) return
    const key = String(candidate.group_key ?? '').trim() || UNGROUPED_KEY
    const existing = groups.get(key)
    if (existing) {
      existing.candidates.push(candidate)
      return
    }
    const label = String(candidate.group ?? '').trim() || key
    groups.set(key, { key, label, candidates: [candidate] })
  })
  return Array.from(groups.values())
}

/**
 * 组内已选数量：按 `aliases` 命中 `selectedIds` 计数。
 * 一个候选无论有几个别名都只算 1（勾 `write_file` 就是 1，不因"同时拦截 3 个别名"而变 3）。
 */
export function groupSelectedCount(
  group: ForbiddenToolSubGroup,
  selectedIds: Set<string> | string[],
): number {
  const selected = selectedIds instanceof Set ? selectedIds : new Set(selectedIds || [])
  return (group?.candidates || []).filter((candidate) =>
    (candidate?.aliases || []).some((alias) => selected.has(String(alias))),
  ).length
}

/**
 * 组级全选 / 取消全选：勾选并入组内全部 `aliases`，取消移除组内全部 `aliases`。
 * 返回新数组：保序（原有项位置不变、新增项按候选顺序追加）、去重、**不修改入参**。
 */
export function applyGroupSelection(
  selected: string[],
  candidates: ForbiddenToolCandidate[],
  checked: boolean,
): string[] {
  const aliases = new Set<string>()
  ;(candidates || []).forEach((candidate) => {
    ;(candidate?.aliases || []).forEach((alias) => aliases.add(String(alias)))
  })

  const result: string[] = []
  const seen = new Set<string>()
  ;(selected || []).forEach((id) => {
    const value = String(id)
    // 取消全选：组内别名一律移除（不触碰 orphan 等组外项）
    if (!checked && aliases.has(value)) return
    if (seen.has(value)) return
    seen.add(value)
    result.push(value)
  })

  if (checked) {
    aliases.forEach((alias) => {
      if (seen.has(alias)) return
      seen.add(alias)
      result.push(alias)
    })
  }
  return result
}

/**
 * 搜索过滤：对 `group_key` / `group` / `id` / `label` / `description` 做大小写不敏感匹配。
 * 粒度为**子组**——组自身命中或组内任一候选命中都保留该组（保留其全部候选，
 * 这样「全选本组」的含义不会随搜索悄悄漂移）；空查询原样返回。
 */
export function filterSubGroups(
  groups: ForbiddenToolSubGroup[],
  query: string,
): ForbiddenToolSubGroup[] {
  const needle = String(query ?? '').trim().toLowerCase()
  if (!needle) return groups || []
  return (groups || []).filter((group) => {
    if (String(group?.key ?? '').toLowerCase().includes(needle)) return true
    if (String(group?.label ?? '').toLowerCase().includes(needle)) return true
    return (group?.candidates || []).some(
      (candidate) =>
        String(candidate?.id ?? '').toLowerCase().includes(needle)
        || String(candidate?.label ?? '').toLowerCase().includes(needle)
        || String(candidate?.description ?? '').toLowerCase().includes(needle),
    )
  })
}
