/**
 * 「禁用资源」页的候选分组纯函数（spec §3.4）。
 *
 * 设计取舍：候选的归属与展示标签（`group_key` / `group`）由后端决定，
 * 前端**只按 `group_key` 聚合、直接渲染 `group`**，不在这里做任何类别中文映射
 * —— 否则又会出现一份与后端平行的硬编码（v1 已吃过三份硬编码漂移的亏）。
 */

export interface ForbiddenToolCandidate {
  id: string
  label: string
  description: string
  /** 内置工具的类别；公共技能候选没有这个概念，故可选（skills 模式也不做类别分流）。 */
  category?: string
  /** 参与选中判定的名字集合；缺省（技能候选只给 id）时由 `candidateAliases` 退化为 `[id]`。 */
  aliases?: string[]
  /** 稳定聚合键：`builtin:<category>` / `api:<group_name|__ungrouped__>` / `mcp:<server_name|__unknown__>` / `skill:__all__`。 */
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
 * 候选项在选中集合里的名字集合：`aliases` 缺省或为空时退化为 `id` 本身。
 *
 * 为什么必须有这条退化：公共技能候选（`skill_candidates`）只给 `id`，没有别名概念。
 * 若这里不退化，`groupSelectedCount` 会恒为 0、`(n/m)` 永远显示 0/2、组卡片永远不变红、
 * 「全选」一个 id 都写不进去——skills 模式整块静默失效。放在纯函数里而不是组件里，
 * 是为了让"怎么算选中"只有一个来源（工具与技能共用同一套判定）。
 */
export function candidateAliases(candidate: ForbiddenToolCandidate): string[] {
  const aliases = (candidate?.aliases || [])
    .map((alias) => String(alias))
    .filter((alias) => alias.length > 0)
  if (aliases.length) return aliases
  const id = String(candidate?.id ?? '')
  return id ? [id] : []
}

/**
 * 组内已选数量：按 `candidateAliases` 命中 `selectedIds` 计数。
 * 一个候选无论有几个别名都只算 1（勾 `write_file` 就是 1，不因"同时拦截 3 个别名"而变 3）。
 */
export function groupSelectedCount(
  group: ForbiddenToolSubGroup,
  selectedIds: Set<string> | string[],
): number {
  const selected = selectedIds instanceof Set ? selectedIds : new Set(selectedIds || [])
  return (group?.candidates || []).filter((candidate) =>
    candidateAliases(candidate).some((alias) => selected.has(alias)),
  ).length
}

/**
 * 组级全选 / 取消全选：勾选并入组内全部名字（别名 / 技能 id），取消移除组内全部名字。
 * 返回新数组：保序（原有项位置不变、新增项按候选顺序追加）、去重、**不修改入参**。
 */
export function applyGroupSelection(
  selected: string[],
  candidates: ForbiddenToolCandidate[],
  checked: boolean,
): string[] {
  const aliases = new Set<string>()
  ;(candidates || []).forEach((candidate) => {
    candidateAliases(candidate).forEach((alias) => aliases.add(alias))
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
 * 已选中但目录里**完全查不到**的名字：必须可见、可解除。
 *
 * 关键：勾选一个能力会写入整组别名（`write_file` → `edit_file` / `apply_patch`），
 * 这些别名不是任何候选的 `id`，但它们是**在用的**配置，不是「历史遗留」——只有
 * 既不是 `id`、也不在任何候选 `aliases` 里的名字才该进历史区。
 */
export function findOrphanIds(
  selected: string[],
  candidates: ForbiddenToolCandidate[],
): string[] {
  const known = new Set<string>()
  ;(candidates || []).forEach((candidate) => {
    if (!candidate) return
    known.add(String(candidate.id))
    candidateAliases(candidate).forEach((alias) => known.add(alias))
  })
  return (selected || []).map((id) => String(id)).filter((id) => !known.has(id))
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

/** 组卡片的色调：有选中 = 整卡红化（一眼看到"这里已经拉黑了东西"），无选中沿用各组基色。 */
export interface GroupToneClasses {
  /** 大组卡片容器 */
  bigCard: string
  /** 子分组卡片容器 */
  subCard: string
  /** 子分组头部（背景 + 下边框） */
  subHead: string
  arrow: string
  dot: string
  title: string
  count: string
  action: string
}

export function groupToneClasses(
  hasSelection: boolean,
  base: 'gray' | 'indigo' = 'gray',
): GroupToneClasses {
  if (hasSelection) {
    // 两种基色收敛到同一套红：避免"组不同则红不同"，红只表示"有选中"这一件事
    return {
      bigCard: 'border-red-200 bg-red-50/40',
      subCard: 'border-red-200',
      subHead: 'bg-red-50 border-b border-red-100',
      arrow: 'text-red-400',
      dot: 'bg-red-500',
      title: 'text-red-700',
      count: 'text-red-500',
      action: 'text-red-600 hover:text-red-800',
    }
  }
  if (base === 'indigo') {
    return {
      bigCard: 'border-gray-150 bg-white',
      subCard: 'border-indigo-100',
      subHead: 'bg-indigo-50/60 border-b border-indigo-100/50',
      arrow: 'text-indigo-400',
      dot: 'bg-indigo-500',
      title: 'text-indigo-700',
      count: 'text-indigo-400',
      action: 'text-indigo-600 hover:text-indigo-800',
    }
  }
  return {
    bigCard: 'border-gray-150 bg-white',
    subCard: 'border-gray-200',
    subHead: 'bg-gray-50 border-b border-gray-100',
    arrow: 'text-gray-400',
    // 内置高危组的圆点本来就是红色（沙箱/命令语义），别被"无选中"改掉
    dot: 'bg-red-500',
    title: 'text-gray-700',
    count: 'text-gray-400',
    action: 'text-red-600 hover:text-red-800',
  }
}
