/**
 * 公共技能「管理员已禁用」的统一判定口径。
 *
 * 后端 `GET /api/portal/skills` 在每条数据上新增 `forbidden: boolean`；管理员恒为 false，
 * 个人技能接口（`/skills/personal`）不带该字段。三处用户挂载入口——会话输入框技能中心、
 * 会话固定资源弹窗（渲染在 ResourceScopeModal）、任务提示词编辑器——必须共用这一份判定，
 * 不允许各自内联 `skill.forbidden`，否则迟早漂移成「一处按布尔判、一处按真值判」。
 *
 * 缺字段一律按**未禁用**处理：旧接口 / 旧缓存 / 个人技能都不带该字段，
 * 误把可用技能锁成不可选，比多显示一次禁用提示的代价大得多。
 */

export interface SkillForbiddenLike {
  /** 后端清单接口下发的禁用标记；仅严格等于布尔 true 才算被禁用 */
  forbidden?: boolean | null
}

/** 「管理员已禁用」小标签文案：三处入口共用，避免同一个状态各写各的说法 */
export const FORBIDDEN_SKILL_BADGE = '管理员已禁用'

/**
 * 严格判等：只有布尔 `true` 算被禁。
 * 刻意不用真值判断——`forbidden: 'false'` 属于真值，那样会把可用技能误锁成不可选。
 */
export function isSkillForbidden(skill?: SkillForbiddenLike | null): boolean {
  return skill?.forbidden === true
}

/**
 * 禁用原因说明（挂在 title 上，让用户知道为什么点不动）。
 * 动作动词按入口传：技能中心是「挂载」，资源网格是「勾选」；未禁用时返回空串，
 * 调用方据此决定要不要渲染 title。
 */
export function forbiddenSkillReason(
  skill?: SkillForbiddenLike | null,
  action = '挂载',
): string {
  if (!isSkillForbidden(skill)) return ''
  return `管理员已禁用该技能，无法${action}`
}
