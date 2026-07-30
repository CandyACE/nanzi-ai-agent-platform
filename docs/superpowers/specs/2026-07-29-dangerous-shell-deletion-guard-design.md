# 危险 Shell 删除命令防护设计

## 背景

当前 NanZi 有两套 Shell 执行路径：旧版 `system_executive_tools.exec_command` 自带一组高危正则拦截，AgentScope 主路径则把 `exec_command` 映射为原生 `Bash`。两套路径的安全判断不一致，且 AgentScope 包装层在 `approval_mode=allow` 时可能在原生 Bash 安全检查之前直接放行。

本设计只处理 Shell 删除类操作的统一决策，不扩大到完整的容器安全加固或一般系统命令治理。

## 目标与非目标

### 目标

1. 删除系统级关键目录或其全量内容时直接硬拒绝。
2. 删除普通文件或普通目录时必须进入用户确认流程；没有确认不得执行。
3. 删除判断覆盖 AgentScope 原生 Bash 和旧版 `exec_command` 入口。
4. `approval_mode=allow`、用户命令白名单或其他通用放行规则都不能绕过删除安全判断。
5. 对 shell 复合命令、路径规范化、通配符和无法静态判断的动态表达式保持 fail-closed 行为。

### 非目标

- 本轮不改 Docker 镜像用户、Linux capabilities、seccomp 或挂载模式。
- 本轮不重新设计所有高危命令（如 `chmod`、`systemctl`、网络扫描）的策略。
- 本轮不允许自动删除普通文件；“普通删除可确认”只意味着交互式确认后允许执行。

## 删除决策模型

统一判断器输出三类结果：

| 决策 | 含义 |
| --- | --- |
| `DENY` | 命中系统级保护目录、保护工作区或全量清空模式，永远不执行。 |
| `ASK` | 是删除/擦除操作，但目标不是受保护的全局根；必须由 PermissionEngine 触发显式确认。 |
| `PASS` | 不是删除类 Shell 操作，交给现有审批、黑名单和 AgentScope 原生策略。 |

判断器只负责删除安全边界，不替代现有的用户/角色 `forbidden_commands`。

## 受保护目标

以下目标本身，以及对其内容的全量清空，返回 `DENY`：

- 文件系统根目录 `/`；
- Unix 系统关键目录：`/bin`、`/boot`、`/dev`、`/etc`、`/home`、`/lib`、`/lib64`、`/opt`、`/proc`、`/root`、`/run`、`/sbin`、`/srv`、`/sys`、`/tmp`、`/usr`、`/var`；
- 当前用户主目录 `~`、`$HOME`；
- 当前 Agent 工作区、仓库根目录及其会话根目录；
- 应用根目录 `/app`、平台数据根目录 `/app/data`、技能根目录和其他已配置的共享挂载根目录；
- 等价的相对路径、规范化后的 `..` 路径，以及指向上述目录的全量通配符（例如 `/*`、`/etc/*`、`/app/data/*`、工作区内的 `*`）。

普通子目录不因位于受保护根目录下而自动硬拒绝。例如，删除 `/tmp/test-dir` 或 `/app/data/uploads/a.txt` 进入 `ASK`，但删除 `/tmp` 或 `/app/data/*` 进入 `DENY`。

路径无法解析、命令替换或脚本控制流导致目标不确定时，返回 `ASK`，不得因为 `approval_mode=allow` 变成自动执行。

## 执行入口与数据流

1. AgentScope `AgentScopeRuntimeTool.check_permissions` 和 `AgentScopeNativeApprovalTool.check_permissions` 在现有工具/命令黑名单之前调用统一判断器。
2. 判断为 `DENY` 时立即返回带 `bypass_immune=True` 的拒绝决策。
3. 判断为 `ASK` 时立即返回带 `bypass_immune=True` 的确认决策，不能先进入 `approval_mode=allow` 分支。
4. 只有 `PASS` 才继续现有的 `forbidden_tools`、`forbidden_commands`、`permission_scope`、原生 AgentScope 检查和审批流程。
5. 旧版 `system_executive_tools.exec_command` 复用同一个判断器，保留已有的非删除高危命令拦截。

这样可保证主 AgentScope 路径和旧版工具路径不会因为各自的正则、审批顺序或工具别名产生不同结果。

## 错误与审批行为

- `DENY` 返回明确原因，例如“禁止删除系统关键目录 `/`”。调用链不得启动子进程。
- `ASK` 返回“删除操作需要确认”及解析出的目标路径。调用链不得在确认前启动子进程。
- 用户/角色策略读取失败继续沿用现有 fail-closed 拒绝逻辑。
- 管理员身份不绕过统一删除判断；管理员仅保留现有业务权限语义，不获得删除系统目录的例外。
- 后台定时任务即使使用 `approval_mode=allow`，也不能静默执行 `ASK` 类删除；没有可用的显式确认时不得继续。

## 测试策略

先写失败测试，再实现最小改动：

1. 纯函数测试：根目录、系统关键目录、主目录、应用数据根、工作区根和全量通配符返回 `DENY`。
2. 普通删除测试：普通文件、普通目录、`/tmp/test-dir`、工作区子目录返回 `ASK`。
3. Shell 组合测试：管道、`&&`、分号、引号、相对路径、`..`、命令替换和无法解析的控制流不会绕过判断。
4. AgentScope 包装器测试：`approval_mode=allow` 对删除仍返回 `ASK`，确认前不调用底层工具；非删除命令保持现有行为。
5. 旧版 `exec_command` 测试：系统级删除硬拒绝，普通删除不直接执行。
6. 回归测试：现有 `rm -rf /`、`shutdown`、PID 1、fork bomb、超时和路径安全测试继续通过。

测试只验证权限决策和底层调用是否被触发，不执行真实删除命令。

## 方案选择

- 方案 A：只扩展旧版正则。改动小，但主 AgentScope Bash 路径仍可能绕过，放弃。
- 方案 B：只依赖 AgentScope 原生 Bash parser。能覆盖主路径，但旧入口和应用动态保护根目录不统一，放弃。
- 方案 C：新增平台统一删除判断器，在两个包装入口的审批最前面调用，并保留现有其他安全策略。选择此方案，改动边界清晰且能确保 `approval_mode=allow` 不绕过删除护栏。

## 验收标准

- `rm -rf /`、`rm -rf /app/data`、`rm -rf /etc/*`、删除当前工作区根目录均直接拒绝且不启动子进程。
- 删除普通文件或普通目录始终进入确认流程；未确认时不执行。
- AgentScope 主路径、旧版入口、定时任务路径均通过同一套删除决策。
- 既有非删除工具权限、用户/角色命令黑名单和现有高危命令测试不回归。
- 运行聚焦测试、`git diff --check`，不启动 `./dev.sh` 或任何服务。
