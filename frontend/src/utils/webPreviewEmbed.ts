/**
 * 网页预览「能否内嵌」决策 —— 刻意保持零运行时依赖（无 axios、无别名导入）。
 *
 * 这样本模块能被 `node --experimental-strip-types` 直接加载，对判定口径做真实行为
 * 断言（见 tests/frontend/web_preview_embed_decision.mjs）。字符串子串断言抓不到
 * 「命中名单但实测可嵌」这类问题，行为测试可以。
 *
 * 判定优先级：**后端实测结论 > 经验名单**。
 *
 * 旧实现只有一份硬编码名单，`www.baidu.com` 命中 `baidu.com` 就直接拦成提示卡片，
 * 而百度首页实测并不下发任何 `X-Frame-Options` / CSP `frame-ancestors`，用户点
 * 「仍尝试在内嵌框架中加载」立刻就正常打开了 —— 提示本身是误报。
 */

/** 常见防嵌套站点：**仅**在实测拿不到结论时作为降级预判依据。 */
export const KNOWN_RESTRICTED_DOMAINS: readonly string[] = [
  'pypi.org',
  'github.com',
  'gitlab.com',
  'google.com',
  'baidu.com',
  'zhihu.com',
  'bilibili.com',
  'x.com',
  'twitter.com',
  'weibo.com',
  'stackoverflow.com',
  'reddit.com',
  'taobao.com',
  'jd.com',
  'qq.com',
  'weixin.qq.com',
  'medium.com',
  'linkedin.com',
  'notion.so',
]

/** 后端实测结论：`true`=可嵌，`false`=会被浏览器拦截，`null`=未取得结论。 */
export interface EmbedProbeOutcome {
  embeddable: boolean | null
  reason?: string
  signals?: Record<string, string>
}

export type EmbedDecisionBasis = 'probe' | 'heuristic'

export interface EmbedDecision {
  /** `true` 时展示受限提示卡片（不渲染 iframe，除非用户点「仍尝试」）。 */
  blocked: boolean
  /** `probe`=平台实测，`heuristic`=经验预判（降级）。 */
  basis: EmbedDecisionBasis
  title: string
  detail: string
  reason: string
  signals: Record<string, string>
}

export interface ResolveEmbedDecisionOptions {
  /**
   * 实测请求仍在进行中。
   *
   * 此时必须**乐观放行**：探测有网络往返延迟，若期间先按名单拦住，
   * 用户就会看到提示卡片闪一下再变成网页，正是本次要修掉的观感。
   */
  pending?: boolean
}

function normalizeHost(host: string | null | undefined): string {
  return String(host ?? '')
    .trim()
    .toLowerCase()
    .replace(/\.$/, '')
}

/** 从任意 URL 中取出小写主机名；无法解析时返回空串。 */
export function hostnameOf(url: string | null | undefined): string {
  const raw = String(url ?? '').trim()
  if (!raw) return ''
  try {
    return normalizeHost(new URL(raw).hostname)
  } catch {
    return ''
  }
}

/**
 * 主机名是否命中经验名单（含子域）。
 *
 * 后缀匹配必须带 `.` 前缀，否则 `baidu.com.evil.com` 会被误判为百度。
 * 注意：命中只代表「可能受限」，**不能**作为拦截的唯一依据。
 */
export function isKnownRestrictedHost(
  host: string,
  domains: readonly string[] = KNOWN_RESTRICTED_DOMAINS,
): boolean {
  const normalized = normalizeHost(host)
  if (!normalized) return false
  return domains.some((domain) => {
    const candidate = normalizeHost(domain)
    if (!candidate) return false
    return normalized === candidate || normalized.endsWith(`.${candidate}`)
  })
}

function buildProbeBlocked(probe: EmbedProbeOutcome): EmbedDecision {
  const reason = probe.reason || '目标站点声明了防嵌套策略'
  return {
    blocked: true,
    basis: 'probe',
    title: '该站点禁止内嵌预览（实测）',
    detail: `平台已实测目标站点的响应头：${reason}。浏览器会拦截在此区域的内嵌展示，推荐直接在新标签页中访问。`,
    reason,
    signals: { ...(probe.signals || {}) },
  }
}

function buildHeuristicBlocked(probe: EmbedProbeOutcome | null | undefined): EmbedDecision {
  const reason = probe?.reason || ''
  const suffix = reason ? `（${reason}）` : ''
  return {
    blocked: true,
    basis: 'heuristic',
    title: '该站点可能禁止内嵌预览',
    detail: `平台未能完成实测${suffix}，依据常见防嵌套站点名单预判该站点可能拒绝内嵌展示。可直接尝试加载，若显示空白或拒绝连接，请在新标签页中打开。`,
    reason,
    signals: {},
  }
}

function buildAllowed(basis: EmbedDecisionBasis, probe: EmbedProbeOutcome | null | undefined): EmbedDecision {
  return {
    blocked: false,
    basis,
    title: '',
    detail: '',
    reason: probe?.reason || '',
    signals: { ...(probe?.signals || {}) },
  }
}

/**
 * 合并「后端实测结论」与「经验名单」，得出是否展示受限卡片的最终决策。
 *
 * 优先级：实测（`probe`）> 探测中乐观放行 > 名单预判。
 * 探测失败时降级到名单，且文案明确标注为「预判」，不再谎称已检测。
 */
export function resolveEmbedDecision(
  host: string | null | undefined,
  probe: EmbedProbeOutcome | null | undefined,
  options: ResolveEmbedDecisionOptions = {},
): EmbedDecision {
  const normalizedHost = normalizeHost(host)

  // 无有效主机名（URL 非法）时预览面板本就不渲染 iframe，不应拦。
  if (!normalizedHost) return buildAllowed('heuristic', probe)

  // 探测进行中：乐观放行，等实测结论回来再决定。
  if (options.pending) return buildAllowed('probe', probe)

  const verdict = probe && typeof probe === 'object' ? probe.embeddable : null

  if (verdict === true) return buildAllowed('probe', probe)
  if (verdict === false) return buildProbeBlocked(probe as EmbedProbeOutcome)

  // 实测未取得结论（不可达、超时、后端不可用）→ 降级到经验名单。
  if (isKnownRestrictedHost(normalizedHost)) return buildHeuristicBlocked(probe)

  return buildAllowed('heuristic', probe)
}
