/**
 * 「禁用资源」tab 徽标的计数口径（用户视角的条目数）——两个页面共用的唯一来源。
 *
 * 为什么不能用 `forbidden_tools.length`：勾一个内置能力会写入**整组别名**
 * （`write_file` → `edit_file` / `apply_patch`，见 forbiddenToolGroups.applyGroupSelection），
 * 数组长度于是虚高成 2～3 倍：界面上只勾了 3 个勾，徽标却写「7」。用户读不懂这个数字，
 * 也就没法用它判断"我到底禁了多少东西"。
 *
 * 口径定义（工具 / 技能一致）：
 *   1. 一个候选（别名组）只要有一个名字被选中，就记 1 条，组内其余别名不再计数；
 *   2. 不在任何候选别名里的选中项（历史遗留、后端手写的名字）各记 1 条；
 *   3. 空白项忽略，重复项去重——徽标描述的是"禁用了哪些东西"，不是数组有多长；
 *   4. 目录未知（还没加载出来 / 旧接口没给候选）时退化为"去重后的选中项数"，
 *      宁可短暂等于旧口径，也不能凭空少算。
 */

import { candidateAliases, type ForbiddenToolCandidate } from './forbiddenToolGroups'
import { countForbiddenCommands } from './forbiddenCommands'

/** 归一成去重、非空的名字数组；null / 非数组 / 元素非字符串一律按空处理（坏数据不得抛错）。 */
function normalizeSelected(selected: string[] | null | undefined): string[] {
  if (!Array.isArray(selected)) return []
  const names: string[] = []
  const seen = new Set<string>()
  selected.forEach((item) => {
    const name = String(item ?? '').trim()
    if (!name || seen.has(name)) return
    seen.add(name)
    names.push(name)
  })
  return names
}

/**
 * 选中项覆盖的条目数：别名组（候选）粒度见文件头。
 * `candidates` 建议传该资源类型的**全量**候选，而不是搜索过滤后的可见项——
 * 过滤只影响展示，不该让徽标数字随搜索框变化。
 */
export function countSelectedEntries(
  selected: string[] | null | undefined,
  candidates: ForbiddenToolCandidate[] | null | undefined,
): number {
  const remaining = new Set(normalizeSelected(selected))
  let count = 0
  ;(candidates || []).forEach((candidate) => {
    if (!candidate) return
    const aliases = candidateAliases(candidate)
    if (!aliases.some((alias) => remaining.has(alias))) return
    count += 1
    aliases.forEach((alias) => remaining.delete(alias))
  })
  return count + remaining.size
}

export interface ForbiddenBadgeInput {
  /** 编辑中的禁用工具（含整组别名） */
  forbiddenTools?: string[] | null
  /** 禁用工具候选目录；缺省时退化为去重计数 */
  toolCandidates?: ForbiddenToolCandidate[] | null
  /** 禁用命令的原始输入文本（按 F9 的解析函数切分后再计数） */
  forbiddenCommandsText?: string | null
  forbiddenSkills?: string[] | null
  /** 公共技能候选目录 */
  skillCandidates?: ForbiddenToolCandidate[] | null
}

/** 徽标总数 = 工具条目数 + 命令条目数 + 技能条目数。 */
export function countForbiddenResourceBadge(input: ForbiddenBadgeInput): number {
  return (
    countSelectedEntries(input?.forbiddenTools, input?.toolCandidates) +
    countForbiddenCommands(input?.forbiddenCommandsText) +
    countSelectedEntries(input?.forbiddenSkills, input?.skillCandidates)
  )
}
