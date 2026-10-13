/**
 * 禁用目录（工具 / 公共技能候选）的加载缓存——同一个接口只发一次请求。
 *
 * 为什么要去重：每个配置页（用户页 / 角色页）都同时挂载两个 `ForbiddenToolCatalog` 实例
 * （工具一个、技能一个），但它们请求的是**同一个接口**，只是取响应的不同字段。
 * 打开一次弹窗就发两次一模一样的请求，纯属浪费，也让后端日志里同一个动作出现两次。
 *
 * 取舍（为什么是「in-flight 复用 + 30s TTL」而不是永久缓存）：
 *   - in-flight 复用解决的是「同一次交互」内的重复请求，语义绝对安全，没有陈旧风险；
 *   - 保留一个短 TTL，是为了让「关掉弹窗又立刻打开」「切到另一个用户再打开」这类
 *     连续交互不重复打网，同时把陈旧窗口压到 30 秒内——候选目录会随平台配置变化
 *     （MCP 工具注册 / 公共技能上下架），一旦权限或目录在别处变更，最多 30 秒后
 *     重新拉取即可，不需要用户清缓存。TTL 到期前也可以用 `invalidateForbiddenCatalog()`
 *     显式失效。
 *   - 失败**不缓存**：否则一次网络抖动会让用户在整个 TTL 窗口里都看到空目录，
 *     而空目录在保存时意味着"没有任何禁用项"。
 *
 * 本模块不依赖 axios / vue：请求函数由调用方注入，方便复用，也便于纯行为测试。
 */

import type { ForbiddenToolCandidate } from './forbiddenToolGroups'

export interface ForbiddenCatalogSnapshot {
  candidates: ForbiddenToolCandidate[]
  skillCandidates: ForbiddenToolCandidate[]
}

/**
 * 请求函数由调用方注入：允许返回任意形状，本模块负责归一化——
 * 否则每个调用方都要重复一遍"字段缺失 / 非数组怎么办"。
 */
export type ForbiddenCatalogFetcher = () => Promise<unknown> | unknown

export interface LoadForbiddenCatalogOptions {
  /** 覆盖默认 TTL（毫秒） */
  ttlMs?: number
  /** 覆盖时钟，仅测试用：TTL 是行为而不是实现细节，必须可被钉住 */
  now?: () => number
}

/** 30 秒：短到不会让用户看到过时候选，长到足以覆盖「开关弹窗」这类连续交互。 */
export const FORBIDDEN_CATALOG_TTL_MS = 30_000

interface ForbiddenCatalogCacheEntry {
  snapshot: ForbiddenCatalogSnapshot
  storedAt: number
}

let cacheEntry: ForbiddenCatalogCacheEntry | null = null
let inFlight: Promise<ForbiddenCatalogSnapshot> | null = null
const listeners = new Set<(snapshot: ForbiddenCatalogSnapshot) => void>()

/** 接口坏形状（缺字段 / 非数组）归一成空数组：调用方不该各自防御同一件事。 */
function normalizeSnapshot(raw: unknown): ForbiddenCatalogSnapshot {
  const source = (raw ?? {}) as Record<string, unknown>
  return {
    candidates: Array.isArray(source.candidates) ? (source.candidates as ForbiddenToolCandidate[]) : [],
    skillCandidates: Array.isArray(source.skillCandidates)
      ? (source.skillCandidates as ForbiddenToolCandidate[])
      : [],
  }
}

/** 同步读取当前缓存（未加载或已失效时返回 null），供徽标计数等渲染路径使用。 */
export function peekForbiddenCatalog(): ForbiddenCatalogSnapshot | null {
  return cacheEntry ? cacheEntry.snapshot : null
}

/**
 * 订阅「目录加载成功」。返回退订函数——页面卸载必须调用，
 * 否则陈旧的回调会一直持有组件状态。单个订阅者抛错不影响其他订阅者。
 */
export function subscribeForbiddenCatalog(
  listener: (snapshot: ForbiddenCatalogSnapshot) => void,
): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

/** 显式失效：下次加载必然重新请求。 */
export function invalidateForbiddenCatalog(): void {
  cacheEntry = null
}

export function loadForbiddenCatalog(
  fetcher: ForbiddenCatalogFetcher,
  options: LoadForbiddenCatalogOptions = {},
): Promise<ForbiddenCatalogSnapshot> {
  const ttlMs = options.ttlMs ?? FORBIDDEN_CATALOG_TTL_MS
  const now = options.now ?? Date.now

  // 顺序很重要：先看 in-flight。否则缓存刚好过期又同时来了两个调用时，
  // 两个调用都会各自发起请求，"去重"在最需要它的时刻失效。
  if (inFlight) return inFlight
  if (cacheEntry && now() - cacheEntry.storedAt < ttlMs) {
    return Promise.resolve(cacheEntry.snapshot)
  }

  inFlight = Promise.resolve()
    .then(() => fetcher())
    .then((raw) => {
      const snapshot = normalizeSnapshot(raw)
      cacheEntry = { snapshot, storedAt: now() }
      inFlight = null
      listeners.forEach((listener) => {
        try {
          listener(snapshot)
        } catch (error) {
          console.warn('forbidden catalog listener failed', error)
        }
      })
      return snapshot
    })
    .catch((error) => {
      // 失败不写缓存，也不通知订阅者：让下一次打开真实重试
      inFlight = null
      throw error
    })

  return inFlight
}
