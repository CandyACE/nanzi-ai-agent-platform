/**
 * 智能体级资源限制（用户/角色 × 单个智能体 × 资源）的共享判定。
 *
 * 平台原先只有一层「全局禁用资源」：拉黑之后该用户在**所有**智能体里都不能用。
 * 本层作用域更细——同一个用户在不同智能体里可以有不同边界，典型场景是智能体已绑定
 * 10 个工具 / 10 个技能 / 10 个 MCP，管理员希望针对「某用户或角色 × 某个智能体」
 * 再排除其中一部分，而不影响该用户在其智能体里的能力。语义仍是「排除」。
 *
 * 这里只放**纯函数**：分组归一化、已选计数、payload 构造、全局禁用项不可选判定、
 * 以及接口路径。用户页 / 角色页 / 弹框都调这一份——各写一份必然漂移成两套判定，
 * 本项目已经为「同一件事两份口径」吃过一次亏（GET 读并集、PUT 写直配）。
 *
 * 与全局禁用的关系是**并集**（全局禁用 ∪ 智能体级禁用），所以本弹框里已全局禁用的项
 * **只读置灰、不可勾选**：排除机制只增不减，在这里「放开」全局禁与会与全局语义打架。
 */

export type AgentRestrictionScopeKind = 'user' | 'role'

/** 候选项：`id` 就是落库的 `resource_id`（工具名或技能 id） */
import { groupToolsForDisplay } from './toolGrouping'

export interface RestrictableResourceItem {
  id: string
  label: string
  /** 已被全局禁用：本弹框里置灰只读（并集语义，全局项无从放开） */
  forbidden_globally: boolean
  /** 自定义 API 工具在注册表里填的业务分组；工具页签据此与智能体编辑页保持同一套分组 */
  group_name?: string
  /**
   * 中文描述。没有它，弹框里每个工具就只是一行裸 id（`system_http_request`），
   * 管理员根本看不出这是什么工具——而智能体编辑页一直显示的是描述。
   */
  description?: string
  /**
   * 本层无法限定该资源（目前只有个人技能）。
   *
   * 权限侧三处过滤全部把个人技能排除在外（清单 `excluded_skill_ids`、显式挂载
   * `drop_forbidden_skill_items`、上下文清洗），因为个人技能与公共技能可能同名，
   * 只按 id 判定会连坐用户自建的那一份。此前界面允许勾选并真的写库，运行时却
   * 任何一处都不读——勾了不生效且查不出原因，所以改为置灰只读。
   */
  not_restrictable?: boolean
  /** 置灰原因，直接展示给管理员 */
  not_restrictable_reason?: string
}

/** 候选清单来自具体某个版本；运行时生效的是已发布版本。 */
export interface AgentRestrictionSourceVersion {
  id: string
  version_number: number | null
  status: string
  is_published: boolean
}

/** 候选目录：分组 + 它来自哪个版本（数量与编辑页对不上时，靠它解释）。 */
export interface AgentRestrictableCatalog {
  groups: RestrictableResourceGroup[]
  sourceVersion: AgentRestrictionSourceVersion | null
}

/** 分组：内置工具 / 自定义 API 工具 / MCP（按 server 一个组）/ 公共技能 / 个人技能……绑什么才有什么，数量由接口决定 */
export interface RestrictableResourceGroup {
  key: string
  label: string
  items: RestrictableResourceItem[]
}

/** 该 (作用域, 智能体) 已配置的限制（GET / PUT 的同一形状） */
export interface AgentRestrictionLists {
  forbidden_tools: string[]
  forbidden_skills: string[]
}

export interface RestrictableGroupSelectionState {
  /** 组内已选（只数可勾选项） */
  selected: number
  /** 组内可勾选项数量（不含全局禁用项） */
  selectable: number
  allSelected: boolean
}

/** payload 结构：只含该智能体的两项限制，覆盖式写入，空数组 = 清空 */
export interface AgentRestrictionPayload {
  forbidden_tools: string[]
  forbidden_skills: string[]
}

/** 缺少分组键时的兜底键（与 forbiddenToolGroups 的兜底同思路：宁可兜底，不可丢条目） */
const GROUP_KEY_FALLBACK_PREFIX = '__restrictable_group_'

/** 归一去重、去空白的字符串数组；null / 非数组一律按空处理（坏数据不得抛错）。 */
export function normalizeSelectedIds(selected: unknown): string[] {
  if (!Array.isArray(selected)) return []
  const result: string[] = []
  const seen = new Set<string>()
  selected.forEach((raw) => {
    const id = String(raw ?? '').trim()
    if (!id || seen.has(id)) return
    seen.add(id)
    result.push(id)
  })
  return result
}

/** 候选项归一化：id 空白的丢弃，label 缺省退化到 id，forbidden_globally 强制成布尔。 */
function normalizeItem(raw: unknown): RestrictableResourceItem | null {
  if (!raw || typeof raw !== 'object') return null
  const record = raw as Record<string, unknown>
  const id = String(record.id ?? '').trim()
  if (!id) return null
  const label = String(record.label ?? '').trim() || id
  const groupName = String(record.group_name ?? '').trim()
  const description = String(record.description ?? '').trim()
  const notRestrictableReason = String(record.not_restrictable_reason ?? '').trim()
  return {
    id,
    label,
    forbidden_globally: Boolean(record.forbidden_globally),
    ...(groupName ? { group_name: groupName } : {}),
    ...(description ? { description } : {}),
    ...(record.not_restrictable ? { not_restrictable: true } : {}),
    ...(notRestrictableReason ? { not_restrictable_reason: notRestrictableReason } : {}),
  }
}

/**
 * 接口响应 → 候选来源版本（老响应没有该字段时返回 null，不编造）。
 *
 * 为什么需要：候选清单来自**某一个具体版本**（优先已发布），而限制是按 agent 维度配的。
 * 管理员正在编辑页改的是草稿版本，两个页面的数量天然可能不同；把来源版本显示出来，
 * 这个差异才是可解释的，而不是看起来像个 bug。
 */
export function readSourceVersion(raw: unknown): AgentRestrictionSourceVersion | null {
  if (!raw || typeof raw !== 'object') return null
  const record = (raw as Record<string, unknown>).source_version
  if (!record || typeof record !== 'object') return null
  const version = record as Record<string, unknown>
  const id = String(version.id ?? '').trim()
  if (!id) return null
  const rawNumber = version.version_number
  const parsedNumber =
    typeof rawNumber === 'number' && Number.isFinite(rawNumber)
      ? rawNumber
      : Number.parseInt(String(rawNumber ?? ''), 10)
  return {
    id,
    version_number: Number.isFinite(parsedNumber) ? parsedNumber : null,
    status: String(version.status ?? '').trim(),
    is_published: Boolean(version.is_published),
  }
}

/** 接口响应 → 候选目录（分组 + 来源版本）。 */
export function normalizeAgentRestrictableCatalog(raw: unknown): AgentRestrictableCatalog {
  return {
    groups: normalizeRestrictableGroups(raw),
    sourceVersion: readSourceVersion(raw),
  }
}

/**
 * 接口响应 → 可渲染分组。
 *
 * 只认整体响应（`{ agent_id, groups: [...] }`）：裸数组不是契约，不猜。
 * 保序、不合并、不硬编码四组——多一个 MCP server 就多一组；无条目的分组不占位。
 */
export function normalizeRestrictableGroups(raw: unknown): RestrictableResourceGroup[] {
  const source = (raw ?? {}) as Record<string, unknown>
  const groups = Array.isArray(source.groups) ? source.groups : []
  const result: RestrictableResourceGroup[] = []

  groups.forEach((rawGroup, index) => {
    if (!rawGroup || typeof rawGroup !== 'object') return
    const record = rawGroup as Record<string, unknown>
    const items = (Array.isArray(record.items) ? record.items : [])
      .map(normalizeItem)
      .filter((item): item is RestrictableResourceItem => item !== null)
    if (!items.length) return
    const key = String(record.key ?? '').trim() || `${GROUP_KEY_FALLBACK_PREFIX}${index}__`
    result.push({ key, label: String(record.label ?? '').trim() || key, items })
  })

  return result
}

/** GET / PUT 回显归一化：坏形状按空数组，不得把 null 当字符串遍历。 */
export function normalizeAgentRestriction(raw: unknown): AgentRestrictionLists {
  const source = (raw ?? {}) as Record<string, unknown>
  return {
    forbidden_tools: normalizeSelectedIds(source.forbidden_tools),
    forbidden_skills: normalizeSelectedIds(source.forbidden_skills),
  }
}

/** 该项是否已被全局禁用（本弹框里只读、不可勾选）。 */
export function isGloballyForbidden(item: RestrictableResourceItem | null | undefined): boolean {
  return Boolean(item?.forbidden_globally)
}

/** 本层无法限定的项（个人技能）：置灰只读，且永不写入 payload。 */
export function isNotRestrictable(item: RestrictableResourceItem | null | undefined): boolean {
  return Boolean(item?.not_restrictable)
}

/**
 * 不该出现在本层记录里的 id 集合：全局禁用项（并集语义下由全局层负责，写进来毫无意义）
 * 与不可限定项（个人技能，运行时任何一处都不读）。
 *
 * 计数、payload、回显清洗共用这一份，避免出现「角标算进去了但保存不提交」这类口径漂移。
 */
function strippedIds(groups: RestrictableResourceGroup[]): Set<string> {
  const ids = new Set<string>()
  ;(groups || []).forEach((group) => {
    ;(group?.items || []).forEach((item) => {
      if (item && (item.forbidden_globally || item.not_restrictable)) ids.add(String(item.id))
    })
  })
  return ids
}

/** 可勾选项 = 既非全局禁用、也非不可限定（个人技能）。页签与分组分母由此而来。 */
export function selectableItems(
  items: RestrictableResourceItem[] | null | undefined,
): RestrictableResourceItem[] {
  return (items || []).filter((item) => !isGloballyForbidden(item) && !isNotRestrictable(item))
}

/**
 * 条目归属哪份后端列表：工具（`forbidden_tools`）还是技能（`forbidden_skills`）。
 *
 * 接口的 groups 不直接带类型字段，但分组键是稳定契约：`builtin_tools` / `mcp:<server_id>`
 * 是工具，`public_skills` / `personal_skills` 是技能。判定只在这里有一份——散在组件里
 * 写前缀判断，等后端加一个技能来源（例如 `org_skills`）就会漏掉。
 */
export function resourceKindOfGroup(
  group: RestrictableResourceGroup | null | undefined,
): 'tools' | 'skills' {
  const key = String(group?.key ?? '').trim().toLowerCase()
  return key === 'skills' || key.endsWith('_skills') ? 'skills' : 'tools'
}

/**
 * 工具页签内按「能力域 → 业务分组 → 兜底」重新聚合。
 *
 * 接口只给到"内置工具 / 自定义 API 工具"两桶，而智能体编辑页展示的是能力域（ChatBI、
 * 知识库检索、联网搜索、浏览器自动化、系统自治工具 …）。两处结构对不上，管理员就无法
 * 对照着判断"我到底限定了哪些"。这里复用 `toolGrouping` 的同一套规则——规则只有一份。
 *
 * 组键统一加 `tools:` 前缀：`resourceKindOfGroup` 靠 `_skills` 后缀区分技能，
 * 这些新键不带该后缀，因此仍被判为工具，选中项照旧写进 `forbidden_tools`。
 */
export function regroupToolGroups(
  groups: RestrictableResourceGroup[] | null | undefined,
): RestrictableResourceGroup[] {
  const items = (groups || []).flatMap((group) => group.items || [])
  return groupToolsForDisplay(
    items,
    (item) => String(item?.id ?? ''),
    (item) => item?.group_name,
  ).map((group) => ({
    key: group.key,
    label: group.label,
    items: group.items,
  }))
}

/** 弹框的三个页签：与「智能体平台」里资源选择的分类保持一致。 */
export type AgentRestrictionTabKey = 'tools' | 'mcp' | 'skills'

export interface AgentRestrictionTab {
  key: AgentRestrictionTabKey
  label: string
  groups: RestrictableResourceGroup[]
}

/**
 * 三个页签**固定存在**：智能体绑什么才有什么，某个页签为空是正常状态。
 * 若按接口返回动态生成页签，"这个智能体为什么没有 SKILLS"就变成了无从判断的疑问；
 * 固定页签 + 空态说明能直接回答它。
 */
export const AGENT_RESTRICTION_TABS: ReadonlyArray<{
  key: AgentRestrictionTabKey
  label: string
  emptyHint: string
}> = [
  { key: 'tools', label: '工具', emptyHint: '该智能体未绑定任何工具。' },
  { key: 'mcp', label: 'MCP', emptyHint: '该智能体未绑定 MCP 工具。' },
  { key: 'skills', label: 'SKILLS', emptyHint: '该智能体未绑定公共技能，也没有个人技能。' },
]

/**
 * 分组归属哪个页签。
 *
 * MCP 组键形如 `mcp:<server_id>`（一个 server 一个组）；技能组键以 `_skills` 结尾
 * （后端新增技能来源时请沿用该后缀，否则会被归到「工具」页签）；其余都是工具
 * （内置工具 `builtin_tools`、自定义 API `api_tools`）。
 */
export function resourceTabOfGroup(
  group: RestrictableResourceGroup | null | undefined,
): AgentRestrictionTabKey {
  const key = String(group?.key ?? '')
    .trim()
    .toLowerCase()
  if (key === 'mcp' || key.startsWith('mcp:')) return 'mcp'
  return key === 'skills' || key.endsWith('_skills') ? 'skills' : 'tools'
}

/** 把接口返回的分组归到三个页签（保序：页签内维持接口给的顺序）。 */
export function groupRestrictionTabs(
  groups: RestrictableResourceGroup[] | null | undefined,
): AgentRestrictionTab[] {
  const buckets: Record<AgentRestrictionTabKey, RestrictableResourceGroup[]> = {
    tools: [],
    mcp: [],
    skills: [],
  }
  ;(groups || []).forEach((group) => {
    buckets[resourceTabOfGroup(group)].push(group)
  })
  return AGENT_RESTRICTION_TABS.map((tab) => ({
    key: tab.key,
    label: tab.label,
    groups: buckets[tab.key],
  }))
}

/** 页签上的计数：分母只算可勾选项（全局已禁项不能勾，不该进分母）。 */
export function tabSelectionState(
  tab: AgentRestrictionTab | null | undefined,
  selected: unknown,
): RestrictableGroupSelectionState {
  const items = (tab?.groups || []).flatMap((group) => group.items || [])
  return groupSelectionState(selected, items)
}

export function tabEmptyHint(key: AgentRestrictionTabKey): string {
  return AGENT_RESTRICTION_TABS.find((tab) => tab.key === key)?.emptyHint || '暂无可限制的资源。'
}

/**
 * 回显清洗：剔除已全局禁用的项（并集语义下写成本层记录毫无意义，而且界面上它是灰的），
 * 保留「已不在目录中」的历史项——那些要展示给用户手动清理，不能静默删除。
 */
export function sanitizeAgentRestrictionLists(
  lists: AgentRestrictionLists | null | undefined,
  groups: RestrictableResourceGroup[] | null | undefined,
): AgentRestrictionLists {
  const normalized = normalizeAgentRestriction(lists)
  const stripped = strippedIds(groups || [])
  const keep = (ids: string[]) => ids.filter((id) => !stripped.has(id))
  return {
    forbidden_tools: keep(normalized.forbidden_tools),
    forbidden_skills: keep(normalized.forbidden_skills),
  }
}

/**
 * 已选项条数（弹框「已选 N 项」与卡片角标共用）：
 *   1. 去重、去空白；
 *   2. 目录已知时剔除全局禁用项——它们由全局层负责，不算本层限制；
 *   3. 目录未知时退化为去重计数（宁可短暂等于旧口径，也不能凭空少算）。
 */
export function countRestrictionEntries(
  selected: unknown,
  groups?: RestrictableResourceGroup[] | null,
): number {
  const ids = normalizeSelectedIds(selected)
  const known = (groups || []).length > 0
  if (!known) return ids.length
  const stripped = strippedIds(groups || [])
  return ids.filter((id) => !stripped.has(id)).length
}

/** 卡片角标总数 = 该智能体禁用的工具数 + 技能数（口径与弹框一致）。 */
export function countAgentRestrictionBadge(
  lists: AgentRestrictionLists | null | undefined,
  groups?: RestrictableResourceGroup[] | null,
): number {
  const normalized = normalizeAgentRestriction(lists)
  return (
    countRestrictionEntries(normalized.forbidden_tools, groups)
    + countRestrictionEntries(normalized.forbidden_skills, groups)
  )
}

/** 组内选中状态：计数与「已全选」判定同源，避免 (n/m) 与按钮文案互相矛盾。 */
export function groupSelectionState(
  selected: unknown,
  items: RestrictableResourceItem[] | null | undefined,
): RestrictableGroupSelectionState {
  const selectedIds = new Set(normalizeSelectedIds(selected))
  const selectable = selectableItems(items)
  const selectedCount = selectable.filter((item) => selectedIds.has(item.id)).length
  return {
    selected: selectedCount,
    selectable: selectable.length,
    allSelected: selectable.length > 0 && selectedCount === selectable.length,
  }
}

/**
 * 组级全选 / 取消全选：
 *   - 勾选只并入**可勾选**项（全局禁用项永远写不进来——「排除只增不减」）；
 *   - 取消移除组内全部 id（含全局项：本层若真存了全局项记录，允许被清掉）。
 * 返回新数组：保序、去重、不修改入参。
 */
export function applyGroupRestrictionSelection(
  selected: unknown,
  items: RestrictableResourceItem[] | null | undefined,
  checked: boolean,
): string[] {
  const groupIds = new Set((items || []).map((item) => item.id))
  const keep = checked ? null : groupIds
  const result: string[] = []
  const seen = new Set<string>()

  normalizeSelectedIds(selected).forEach((id) => {
    if (keep && keep.has(id)) return
    if (seen.has(id)) return
    seen.add(id)
    result.push(id)
  })

  if (checked) {
    selectableItems(items).forEach((item) => {
      if (seen.has(item.id)) return
      seen.add(item.id)
      result.push(item.id)
    })
  }

  return result
}

/** 从选择集里剔除指定 id：用于「一键清理已不再绑定的历史项」。 */
export function excludeSelectedIds(selected: unknown, ids: unknown): string[] {
  const excluded = new Set(normalizeSelectedIds(ids))
  return normalizeSelectedIds(selected).filter((id) => !excluded.has(id))
}

/** 已选中但目录里查不到的 id：该智能体已不再绑定（工具改名 / 解绑 / 技能下架）。 */
export function findUnboundRestrictionIds(
  selected: unknown,
  groups: RestrictableResourceGroup[] | null | undefined,
): string[] {
  const known = new Set<string>()
  ;(groups || []).forEach((group) => {
    ;(group?.items || []).forEach((item) => known.add(String(item?.id ?? '')))
  })
  return normalizeSelectedIds(selected).filter((id) => !known.has(id))
}

/**
 * 搜索：按分组键 / 分组名 / 条目 id / 条目名做大小写不敏感匹配；粒度为**分组**
 * （命中任一即保留整组，这样「全选本组」的含义不随搜索漂移）；空查询原样返回。
 */
export function filterRestrictableGroups(
  groups: RestrictableResourceGroup[] | null | undefined,
  query: string,
): RestrictableResourceGroup[] {
  const needle = String(query ?? '').trim().toLowerCase()
  if (!needle) return groups || []
  return (groups || []).filter((group) => {
    if (String(group?.key ?? '').toLowerCase().includes(needle)) return true
    if (String(group?.label ?? '').toLowerCase().includes(needle)) return true
    return (group?.items || []).some(
      (item) =>
        String(item?.id ?? '').toLowerCase().includes(needle)
        || String(item?.label ?? '').toLowerCase().includes(needle),
    )
  })
}

/**
 * 保存 payload：**只含该智能体的两项限制**。
 *
 * - 覆盖式语义，空数组 = 清空；
 * - 去重去空、剔除全局禁用项（由全局层负责，写进来只会制造重复口径）；
 * - 不在目录里的历史项**保留**：它们仍是用户已配置的限制，删除必须由用户显式操作；
 * - 绝不带 `forbidden_commands`（命令禁用只由全局禁用资源管理）或任何权限字段。
 */
export function buildAgentRestrictionPayload(
  lists: AgentRestrictionLists | null | undefined,
  groups?: RestrictableResourceGroup[] | null,
): AgentRestrictionPayload {
  const normalized = normalizeAgentRestriction(lists)
  const stripped = strippedIds(groups || [])
  const keep = (ids: string[]) => ids.filter((id) => !stripped.has(id))
  return {
    forbidden_tools: keep(normalized.forbidden_tools),
    forbidden_skills: keep(normalized.forbidden_skills),
  }
}

/**
 * 接口前缀：智能体级限制全部挂在 management 下（与 /users/{id}/permissions 同族，
 * 后端实现见 app/api/portal/endpoints/management.py 的 agent-restrictions 段）。
 */
const AGENT_RESTRICTABLE_BASE = '/api/portal/management/agents'
const USER_RESTRICTION_BASE = '/api/portal/management/users'
const ROLE_RESTRICTION_BASE = '/api/portal/management/roles'

const encodeSegment = (value: unknown) => encodeURIComponent(String(value ?? '').trim())

/**
 * GET 该智能体实际绑定的候选清单（内置工具 / 自定义 API 工具 / MCP 按 server 分组 /
 * 公共技能 / 个人技能——绑什么才有什么，组数量不固定）。
 *
 * **必须带视角参数**：每项的 `forbidden_globally` 是相对「这个用户 / 这个角色」的全局禁用
 * 而言的。不带 `user_id` / `role_id` 时后端无从回填，全局禁用项就不会置灰——管理员会
 * 以为自己能在这里放开全局禁（排除机制只增不减，这里绝不能放开）。
 */
export function agentRestrictableResourcesPath(
  kind: AgentRestrictionScopeKind,
  scopeId: unknown,
  agentId: unknown,
): string {
  const scopeParam = kind === 'role' ? 'role_id' : 'user_id'
  return `${AGENT_RESTRICTABLE_BASE}/${encodeSegment(agentId)}/restrictable-resources`
    + `?${scopeParam}=${encodeSegment(scopeId)}`
}

/** GET / PUT 某用户或某角色在该智能体上的限制。 */
export function agentRestrictionPath(
  kind: AgentRestrictionScopeKind,
  scopeId: unknown,
  agentId: unknown,
): string {
  const base = kind === 'role' ? ROLE_RESTRICTION_BASE : USER_RESTRICTION_BASE
  return `${base}/${encodeSegment(scopeId)}/agent-restrictions/${encodeSegment(agentId)}`
}

const AGENT_RESTRICTION_COUNTS_PATH = '/api/portal/management/agent-restrictions/counts'

/**
 * 一次取多个智能体的限制清单（权限页卡片角标用）。
 *
 * 逐个 GET 会让打开一次权限页发出 N 个请求（N = 已授权智能体数），所以后端提供批量口径。
 * 返回结构与单智能体 GET 相同（**清单**而不是计数），这样角标与弹框能复用同一个计数函数：
 * 若后端直接给数字，就无法剔除"全局已禁用"项，角标会比弹框里实际可选的项多。
 */
export function agentRestrictionCountsPath(
  kind: AgentRestrictionScopeKind,
  scopeId: unknown,
  agentIds: unknown[],
): string {
  const scopeParam = kind === 'role' ? 'role_id' : 'user_id'
  const ids = (agentIds || []).map((id) => String(id)).filter(Boolean)
  return `${AGENT_RESTRICTION_COUNTS_PATH}?${scopeParam}=${encodeSegment(scopeId)}`
    + `&agent_ids=${encodeURIComponent(ids.join(','))}`
}

/**
 * 候选清单的缓存键必须带视角：`forbidden_globally` 随用户 / 角色而异，
 * 只按 agent_id 缓存会让下一个打开弹框的管理员看到上一个人的置灰结果。
 */
export function agentRestrictableCatalogCacheKey(
  kind: AgentRestrictionScopeKind,
  scopeId: unknown,
  agentId: unknown,
): string {
  return `catalog:${agentRestrictionCacheKey(kind, scopeId, agentId)}`
}

/** 缓存键：同一 id 的用户与角色必须落在不同槽位，否则会互相读到对方的限制。 */
export function agentRestrictionCacheKey(
  kind: AgentRestrictionScopeKind,
  scopeId: unknown,
  agentId: unknown,
): string {
  return `${kind}:${String(scopeId ?? '').trim()}:${String(agentId ?? '').trim()}`
}
