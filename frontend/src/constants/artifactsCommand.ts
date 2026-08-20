/** 「我的产出」系统 slash 指令 */
export const MY_ARTIFACTS_SLASH_COMMAND = "/my-artifacts";

export const MY_ARTIFACTS_SYSTEM_COMMAND_ID = "sys_my_artifacts";

export function isMyArtifactsSlashCommand(cmd: string): boolean {
  const normalized = String(cmd || "").trim();
  return normalized === MY_ARTIFACTS_SLASH_COMMAND || normalized === "/产出";
}