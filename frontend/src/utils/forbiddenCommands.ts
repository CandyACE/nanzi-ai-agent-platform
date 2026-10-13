/**
 * 禁用命令关键字：解析与计数的单一来源。
 *
 * 原本「保存」与「tab 徽标计数」各写一份解析必然漂移，这里抽成共享函数。
 * 语义与旧内联实现逐字一致：**只按英文逗号切分**，去空白、丢空项。
 */

export function parseForbiddenCommands(text: string | null | undefined): string[] {
  return String(text ?? '')
    .split(',')
    .map((cmd) => cmd.trim())
    .filter((cmd) => cmd.length > 0)
}

export function countForbiddenCommands(text: string | null | undefined): number {
  return parseForbiddenCommands(text).length
}
