/** Parse create_skills success marker from tool output. */

export type SkillCreatedInfo = {
  skill_id: string
  scope: 'personal' | 'global'
  name: string
}

const MARKER_RE = /NANZI_SKILL_CREATED:(\{.*?\})(?:\s|$)/
// 同一标记会随工具输出长期保留在多条历史消息里，需要能取「最新一次」而不是永远第一个。
const MARKER_RE_GLOBAL = /NANZI_SKILL_CREATED:(\{.*?\})(?=\s|$)/g

function toInfo(rawPayload: string | undefined): SkillCreatedInfo | null {
  if (!rawPayload) return null
  try {
    const payload = JSON.parse(rawPayload)
    const skillId = String(payload.skill_id || '').trim()
    if (!skillId) return null
    const scope = String(payload.scope || 'personal').toLowerCase() === 'global' ? 'global' : 'personal'
    return {
      skill_id: skillId,
      scope,
      name: String(payload.name || skillId),
    }
  } catch {
    return null
  }
}

export function parseSkillCreatedMarker(text: string | null | undefined): SkillCreatedInfo | null {
  if (!text) return null
  const match = MARKER_RE.exec(String(text))
  return toInfo(match?.[1])
}

/**
 * 解析「最后一次」创建标记。
 *
 * 视图侧扫描的是整个会话历史，而标记会随工具输出长期保留；沿用首个匹配会导致
 * 创建过多个技能时，横幅永远显示最早那一个，因此这里取最后一个匹配。
 */
export function parseLatestSkillCreatedMarker(
  text: string | null | undefined,
): SkillCreatedInfo | null {
  if (!text) return null
  const source = String(text)
  MARKER_RE_GLOBAL.lastIndex = 0
  let latest: SkillCreatedInfo | null = null
  let match: RegExpExecArray | null
  while ((match = MARKER_RE_GLOBAL.exec(source)) !== null) {
    const info = toInfo(match[1])
    if (info) latest = info
  }
  return latest
}

export function personalSkillsEditUrl(skillId: string): string {
  const params = new URLSearchParams({ tab: 'skills', skill_id: skillId })
  return `/dashboard/personal?${params.toString()}`
}

const NOTIFY_STORAGE_PREFIX = 'nanzi.skillCreatedBanner.notified:'

export type SkillNotifyGate = {
  /** 该 skill_id 首次出现时返回 true（并立即记为已提示），否则 false。 */
  shouldNotify: (skillId: string) => boolean
  /** 显式记为已提示（用户关闭横幅 / 已完成挂载）。 */
  mark: (skillId: string) => void
}

function readNotified(storageKey: string): Set<string> {
  try {
    const raw = window.localStorage.getItem(storageKey)
    const parsed = raw ? JSON.parse(raw) : null
    return Array.isArray(parsed) ? new Set(parsed.map(String)) : new Set()
  } catch {
    return new Set()
  }
}

function writeNotified(storageKey: string, ids: Set<string>): void {
  try {
    window.localStorage.setItem(storageKey, JSON.stringify([...ids]))
  } catch {
    // 隐私模式 / 存储被禁用：静默退化为内存去重
  }
}

/**
 * 「已创建个人技能」横幅的去重闸门（按会话隔离、可持久化）。
 *
 * 横幅本是一次性提示，但 `NANZI_SKILL_CREATED` 标记会随消息历史长期存在，而视图侧
 * 的 watch 在每次 messages 变化（发消息、流式回复、刷新加载历史、切回会话）时都会
 * 重新解析整个历史；因此必须按 skill_id 去重，否则用户刚关掉就又弹出来，刷新页面
 * 还会再弹一次——这正是「老出现」的原因。
 */
export function createSkillNotifyGate(
  resolveConversationId?: () => string | number | null | undefined,
): SkillNotifyGate {
  let cachedKey = ''
  let notified = new Set<string>()

  const currentKey = () =>
    NOTIFY_STORAGE_PREFIX + (String(resolveConversationId?.() ?? '').trim() || '__default__')

  const current = () => {
    const key = currentKey()
    if (key !== cachedKey) {
      cachedKey = key
      notified = readNotified(key)
    }
    return notified
  }

  const remember = (skillId: string): boolean => {
    const id = String(skillId || '').trim()
    if (!id) return false
    const ids = current()
    if (ids.has(id)) return false
    ids.add(id)
    writeNotified(currentKey(), ids)
    return true
  }

  return {
    shouldNotify: remember,
    mark: (skillId: string) => {
      remember(skillId)
    },
  }
}
