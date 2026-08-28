export interface ToolPermissionDisplayInput {
  toolName?: string;
  args?: Record<string, unknown>;
  details?: string;
}

export interface ToolPermissionDisplay {
  toolName: string;
  toolLabel: string;
  displayTitle: string;
  summary: string;
  riskLabel: string;
  riskTone: "low" | "standard";
  scopeLabel: string;
  impactDescription: string;
  commandText: string;
  parameterText: string;
  commandCount: number;
  isReadOnly: boolean;
  /** 单条检查命令使用紧凑确认布局，但不代表风险级别已被放宽。 */
  isCompact: boolean;
}

const READ_ONLY_SHELL_COMMANDS = new Set([
  "date",
  "df",
  "echo",
  "env",
  "free",
  "grep",
  "head",
  "hostname",
  "id",
  "nproc",
  "ps",
  "pwd",
  "sort",
  "tail",
  "uname",
  "uptime",
  "wc",
  "whoami",
]);

const SHELL_TOOL_NAMES = new Set(["bash", "exec_command", "shell", "sh"]);
const SYSTEM_STATUS_COMMANDS = new Set(["df", "free", "nproc", "ps", "uptime"]);
const COMPACT_PROC_FILES = new Set([
  "/proc/cpuinfo",
  "/proc/diskstats",
  "/proc/loadavg",
  "/proc/meminfo",
  "/proc/mounts",
  "/proc/stat",
  "/proc/uptime",
  "/proc/version",
]);

function stringifyArgs(args: Record<string, unknown> | undefined): string {
  if (!args || Object.keys(args).length === 0) return "";
  try {
    return JSON.stringify(args, null, 2);
  } catch {
    return String(args);
  }
}

function extractCommand(args: Record<string, unknown> | undefined): string {
  if (!args) return "";
  const command = args.command;
  if (typeof command === "string") return command.trim();
  const input = args.input;
  return typeof input === "string" ? input.trim() : "";
}

function splitShellSegments(command: string): string[] {
  return command
    .split(/\r?\n|&&|\|\||;/)
    .map((segment) => segment.trim())
    .filter(Boolean);
}

function firstCommandName(segment: string): string {
  const pipelineStart = segment.split("|")[0]?.trim() || "";
  const withoutEnv = pipelineStart.replace(/^(?:[A-Za-z_][A-Za-z0-9_]*=[^\s]+\s+)+/, "");
  return withoutEnv.split(/\s+/)[0]?.toLowerCase() || "";
}

function isReadOnlyShellCommand(command: string): boolean {
  if (!command) return false;
  // Any redirection, command substitution or backtick makes the display
  // conservative. The backend remains the source of truth for permissions.
  if (/[<>`]|\$\(/.test(command)) return false;
  const segments = splitShellSegments(command);
  if (segments.length === 0) return false;
  return segments.every((segment) =>
    segment
      .split("|")
      .map((part) => firstCommandName(part))
      .every((name) => READ_ONLY_SHELL_COMMANDS.has(name)),
  );
}

function shellCommandNames(command: string): Set<string> {
  return new Set(
    splitShellSegments(command).flatMap((segment) =>
      segment.split("|").map((part) => firstCommandName(part)),
    ),
  );
}

function countShellChecks(command: string): number {
  const segments = splitShellSegments(command);
  const checks = segments.filter((segment) => firstCommandName(segment) !== "echo");
  return checks.length || segments.length;
}

function isCompactShellCommand(command: string): boolean {
  if (!command || /[<>`]|\$\(|&&|\|\||;/.test(command)) return false;
  const segments = splitShellSegments(command);
  if (segments.length !== 1) return false;

  const segment = segments[0] || "";
  const commandName = firstCommandName(segment);
  if (READ_ONLY_SHELL_COMMANDS.has(commandName)) return true;
  if (commandName !== "cat") return false;

  const parts = segment.split(/\s+/).filter(Boolean);
  return parts.length === 2 && COMPACT_PROC_FILES.has(parts[1] || "");
}

export function getToolPermissionDisplay(
  input: ToolPermissionDisplayInput,
): ToolPermissionDisplay {
  const toolName = String(input.toolName || "工具").trim() || "工具";
  const toolLabel = toolName;
  const normalizedToolName = toolName.toLowerCase();
  const commandText = extractCommand(input.args);
  const isShell = SHELL_TOOL_NAMES.has(normalizedToolName);
  const isReadOnly = isShell && isReadOnlyShellCommand(commandText);
  const commandCount = commandText ? countShellChecks(commandText) : 0;
  const isCompact = isShell && commandCount === 1 && isCompactShellCommand(commandText);
  const commandNames = shellCommandNames(commandText);
  const isSystemStatusCheck = [...SYSTEM_STATUS_COMMANDS].every((name) => commandNames.has(name));

  if (isReadOnly) {
    const displayTitle = isSystemStatusCheck ? "读取服务器状态" : "执行只读检查";
    const summary = isSystemStatusCheck
      ? "读取当前运行环境的 CPU、内存、磁盘和进程信息"
      : "执行只读 Bash 命令，不修改文件或服务";
    return {
      toolName,
      toolLabel,
      displayTitle,
      summary,
      riskLabel: "低风险 · 只读",
      riskTone: "low",
      scopeLabel: "当前运行环境",
      impactDescription: "仅读取当前运行环境，不修改文件或服务",
      commandText,
      parameterText: stringifyArgs(input.args),
      commandCount,
      isReadOnly: true,
      isCompact,
    };
  }

  return {
    toolName,
    toolLabel,
    displayTitle: `执行 ${toolName}`,
    summary: isShell
      ? "将执行一条需要授权的 Bash 命令"
      : "将调用该工具，并根据工具参数执行对应操作",
    riskLabel: "需要确认",
    riskTone: "standard",
    scopeLabel: "当前运行环境",
    impactDescription: "执行范围取决于工具权限和提交的参数",
    commandText,
    parameterText: stringifyArgs(input.args) || String(input.details || "").replace(/^参数:\s*/, ""),
    commandCount,
    isReadOnly: false,
    isCompact,
  };
}
