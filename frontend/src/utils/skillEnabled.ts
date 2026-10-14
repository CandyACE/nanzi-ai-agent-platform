/**
 * 技能 `enabled` 的**唯一**前端判定入口，与后端
 * `app/utils/skill_metadata.py:is_skill_enabled` 逐字同构。
 *
 * 为什么必须统一：`enabled` 在 frontmatter / JSON 里是字符串，但人工编辑 SKILL.md 时
 * 完全可能写成 `False` / `0` / `off` / `no`。后端只认 `{1,true,yes,on}` 为启用（真值
 * 白名单），而前端此前有 4 套口径，导致**两个方向都会骗人**：
 *
 *   - `enabled: "False"` / `"0"` / `"no"` / `"off"`：后端判定为**禁用**，前端用
 *     `!== 'false'` 这类黑名单比较却认成**启用** → 管理界面显示"已启用"、会话菜单里
 *     也能勾选，但运行时根本不加载。用户会以为开关坏了。
 *   - `enabled: "yes"` / `"on"`：后端判定为**启用**，而会话资源菜单的白名单只认
 *     `true/1`，技能被直接过滤掉 → 明明启用了却从列表里消失，无从勾选。
 *
 * 判定写成 `defaultValue` 可配是为了与后端签名对齐：元数据缺失时按启用处理（技能默认
 * 启用），只有显式读取某个"必须明确标记"的场景才传 false。
 */
const TRUTHY_FLAGS = new Set(['1', 'true', 'yes', 'on'])

export const isSkillEnabled = (enabled: unknown, defaultValue = true): boolean => {
  if (enabled === null || enabled === undefined) return defaultValue
  if (typeof enabled === 'boolean') return enabled
  return TRUTHY_FLAGS.has(String(enabled).trim().toLowerCase())
}
