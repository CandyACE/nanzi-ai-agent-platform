/**
 * 智能体级限制与其候选清单的请求去重缓存——沿用 `forbiddenCatalogCache.ts` 的模式。
 *
 * 为什么需要：
 *   - 权限弹框「智能体」那一排卡片都要显示已禁数量角标，同一个智能体在一次交互里
 *     可能被「角标计数」与「打开弹框」同时请求；
 *   - 候选清单（内置工具 / MCP / 技能）在一次弹框里会被搜索、分区渲染多次引用。
 * 没有去重就会对同一个 (作用域, 智能体) 连打多次 GET。
 *
 * 取舍（与 forbiddenCatalogCache 一致）：
 *   - in-flight 复用解决「同一次交互」内的重复请求，语义绝对安全；
 *   - 30s TTL 让「关掉弹框又立刻打开」「切到另一个用户再打开」不重复打网，
 *     同时把陈旧窗口压到 30 秒内；
 *   - 失败**不缓存**：一次网络抖动不该让用户在整个 TTL 窗口里看到空限制
 *     （空限制在语义上等于「什么都没禁」，保存时更危险）；
 *   - PUT 成功后用 `writeAgentRestriction` 直接回填：接口已经返回了写进去的内容，
 *     没必要再 GET 一次。
 *
 * 本模块不依赖 axios / vue：请求函数由调用方注入，便于复用与纯行为测试。
 */

import {
  normalizeAgentRestriction,
  normalizeAgentRestrictableCatalog,
  type AgentRestrictionLists,
  type AgentRestrictableCatalog,
} from './agentRestrictions'

export const AGENT_RESTRICTION_TTL_MS = 30_000

export interface AgentRestrictionLoadOptions {
  /** 覆盖默认 TTL（毫秒） */
  ttlMs?: number
  /** 覆盖时钟，仅测试用：TTL 是行为而不是实现细节，必须可被钉住 */
  now?: () => number
}

/** 请求函数由调用方注入：允许返回任意形状，本模块负责归一化。 */
export type AgentResourceFetcher = () => Promise<unknown> | unknown

interface CacheEntry<T> {
  snapshot: T
  storedAt: number
}

const listsCache = new Map<string, CacheEntry<AgentRestrictionLists>>()
const listsInFlight = new Map<string, Promise<AgentRestrictionLists>>()
const catalogCache = new Map<string, CacheEntry<AgentRestrictableCatalog>>()
const catalogInFlight = new Map<string, Promise<AgentRestrictableCatalog>>()

/** 同步读取已缓存的限制（未加载 / 已失效返回 null），供角标计数等渲染路径使用。 */
export function peekAgentRestriction(key: string): AgentRestrictionLists | null {
  const entry = listsCache.get(key)
  return entry ? entry.snapshot : null
}

/**
 * 同步读取已缓存的候选清单，未加载返回 null。
 * `key` 用 `agentRestrictableCatalogCacheKey(kind, scopeId, agentId)`：
 * `forbidden_globally` 随用户 / 角色而异，只按 agent_id 缓存会串号。
 */
export function peekAgentRestrictableCatalog(key: string): AgentRestrictableCatalog | null {
  const entry = catalogCache.get(key)
  return entry ? entry.snapshot : null
}

/** 显式失效：下次加载必然重新请求。不传 key 时清空全部（作用域切换、退出时用）。 */
export function invalidateAgentRestriction(key?: string): void {
  if (key === undefined) listsCache.clear()
  else listsCache.delete(key)
}

export function invalidateAgentRestrictableCatalog(key?: string): void {
  if (key === undefined) catalogCache.clear()
  else catalogCache.delete(key)
}

/** PUT 成功后回填：归一化后写入，角标立刻正确，重新打开弹框也不必再 GET。 */
export function writeAgentRestriction(key: string, lists: unknown): AgentRestrictionLists {
  const snapshot = normalizeAgentRestriction(lists)
  listsCache.set(key, { snapshot, storedAt: Date.now() })
  return snapshot
}

export function loadAgentRestriction(
  key: string,
  fetcher: AgentResourceFetcher,
  options: AgentRestrictionLoadOptions = {},
): Promise<AgentRestrictionLists> {
  const ttlMs = options.ttlMs ?? AGENT_RESTRICTION_TTL_MS
  const now = options.now ?? Date.now

  // 顺序很重要：先看 in-flight，否则「缓存刚好过期 + 同时两个调用」时去重会在最需要它的时刻失效
  const pending = listsInFlight.get(key)
  if (pending) return pending
  const cached = listsCache.get(key)
  if (cached && now() - cached.storedAt < ttlMs) return Promise.resolve(cached.snapshot)

  const request = Promise.resolve()
    .then(() => fetcher())
    .then((raw) => {
      const snapshot = normalizeAgentRestriction(raw)
      listsCache.set(key, { snapshot, storedAt: now() })
      listsInFlight.delete(key)
      return snapshot
    })
    .catch((error) => {
      // 失败不写缓存，也不留 in-flight：让下一次打开真实重试
      listsInFlight.delete(key)
      throw error
    })

  listsInFlight.set(key, request)
  return request
}

export function loadAgentRestrictableCatalog(
  key: string,
  fetcher: AgentResourceFetcher,
  options: AgentRestrictionLoadOptions = {},
): Promise<AgentRestrictableCatalog> {
  const ttlMs = options.ttlMs ?? AGENT_RESTRICTION_TTL_MS
  const now = options.now ?? Date.now

  const pending = catalogInFlight.get(key)
  if (pending) return pending
  const cached = catalogCache.get(key)
  if (cached && now() - cached.storedAt < ttlMs) return Promise.resolve(cached.snapshot)

  const request = Promise.resolve()
    .then(() => fetcher())
    .then((raw) => {
      const snapshot = normalizeAgentRestrictableCatalog(raw)
      catalogCache.set(key, { snapshot, storedAt: now() })
      catalogInFlight.delete(key)
      return snapshot
    })
    .catch((error) => {
      catalogInFlight.delete(key)
      throw error
    })

  catalogInFlight.set(key, request)
  return request
}
