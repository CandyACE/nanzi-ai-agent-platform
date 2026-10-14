/**
 * 接口错误详情 → 一句人话。
 *
 * 起因是两处真实的坏体验：用户页把 `detail` 直接塞进 toast，FastAPI 422 的 detail 是
 * `[{loc, msg, type}, ...]`，界面于是显示 `[object Object]`；角色页更省事，只说
 * 「保存权限失败」——管理员既不知道坏在哪一项，也不知道是不是自己输入的问题。
 *
 * 处理顺序：数组 detail（422）→ 字符串 detail（业务错误）→ detail.message/msg
 * → 顶层 message → 兜底文案。任何分支都不允许把对象直接转成字符串。
 */

/** 字段名 → 界面上的说法；未登记的字段沿用原始字段名，不丢信息。 */
export const API_ERROR_FIELD_LABELS: Record<string, string> = {
  forbidden_tools: '禁用工具',
  forbidden_commands: '禁用命令关键字',
  forbidden_skills: '禁用技能',
  models: '可用模型',
  agents: '智能体',
  datasets: '知识库',
  metadata: '数据集',
  apis: '外部API',
  menus: '菜单',
  elements: '功能权限',
  role_ids: '业务角色',
  user_name: '用户名',
  real_name: '姓名',
  email: '邮箱',
}

/** 只详细展开前几条：toast 放不下二十行，剩下的收敛成计数。 */
const MAX_DETAIL_ITEMS = 3

function fieldOf(loc: unknown): string {
  // FastAPI 的 loc 形如 ['body', 'models', 2]：数字是数组下标，真正有意义的是它前面那个名字
  if (!Array.isArray(loc)) return ''
  for (let index = loc.length - 1; index >= 0; index -= 1) {
    const segment = loc[index]
    if (typeof segment !== 'string') continue
    if (segment === 'body' || segment === 'query' || segment === 'path' || segment === 'header') continue
    return segment
  }
  return ''
}

function labelOf(field: string): string {
  return API_ERROR_FIELD_LABELS[field] || field
}

/** 单条 422 记录 → 一句话；识别不出类型时退回原始 msg（至少不是 [object Object]）。 */
function describeValidationItem(item: unknown): string {
  if (!item || typeof item !== 'object') return String(item ?? '')
  const record = item as Record<string, unknown>
  const field = fieldOf(record.loc)
  const label = field ? labelOf(field) : ''
  const message = typeof record.msg === 'string' ? record.msg.trim() : ''
  const type = typeof record.type === 'string' ? record.type : ''

  const tooLong = /at most (\d+) characters?/i.exec(message)
  if (type === 'string_too_long' || tooLong) {
    const limit = tooLong ? tooLong[1] : ''
    return limit ? `${label || '该项'}长度不能超过 ${limit} 个字符` : `${label || '该项'}过长`
  }
  if (type === 'missing') return `${label || '必填项'}不能为空`
  if (/(_type|_parsing|_error)$/.test(type) && message === '') return `${label || '该项'}格式不正确`
  if (/(string_type|list_type|int_type|bool_type|_parsing)$/.test(type)) {
    return `${label || '该项'}格式不正确`
  }
  if (message) return label ? `${label}：${message}` : message
  return label || '请求参数不合法'
}

export function extractApiErrorDetail(payload: unknown, fallback = '操作失败'): string {
  const record = (payload ?? {}) as Record<string, unknown>
  const detail = record.detail

  if (Array.isArray(detail)) {
    const sentences = detail
      .map((item) => describeValidationItem(item))
      .map((text) => text.trim())
      .filter((text) => text.length > 0)
    if (!sentences.length) return fallback
    const head = sentences.slice(0, MAX_DETAIL_ITEMS).join('；')
    const rest = sentences.length - MAX_DETAIL_ITEMS
    return rest > 0 ? `${head}；其余 ${rest} 项不合法` : head
  }

  if (typeof detail === 'string' && detail.trim()) return detail.trim()

  if (detail && typeof detail === 'object') {
    const nested = detail as Record<string, unknown>
    for (const key of ['message', 'msg', 'detail']) {
      const value = nested[key]
      if (typeof value === 'string' && value.trim()) return value.trim()
    }
  }

  const message = record.message
  if (typeof message === 'string' && message.trim()) return message.trim()

  return fallback
}
