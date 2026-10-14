/**
 * 禁用命令关键字：解析与计数的单一来源。
 *
 * 原本「保存」与「tab 徽标计数」各写一份解析必然漂移，这里抽成共享函数。
 *
 * 分隔符集合 = 人真的会输入的那些：英文逗号 / 中文逗号 / 顿号 / 中英文分号 / 换行。
 * 只认英文逗号的代价是静默失效——「rm，shutdown」会被当成一个关键字存下去，
 * 后端按 shlex 分词做精确匹配，于是它永远命不中任何命令：保存成功、界面无异常、
 * 运行时完全不拦截，管理员以为自己已经禁掉了 shutdown。
 */

/** 一个或多个分隔符连续出现都算一次切分（`rm,,,mv` 与 `rm,mv` 等价）。 */
const COMMAND_SEPARATORS = /[,，、;；\r\n]+/

export function parseForbiddenCommands(text: string | null | undefined): string[] {
  return String(text ?? '')
    .split(COMMAND_SEPARATORS)
    .map((cmd) => cmd.trim())
    .filter((cmd) => cmd.length > 0)
}

export function countForbiddenCommands(text: string | null | undefined): number {
  return parseForbiddenCommands(text).length
}
