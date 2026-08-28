# Agent 工具调用统一超时实施计划

## 目标

通过 AgentScope 运行时统一包装所有纳入 Agent 执行链的工具调用，增加系统配置 `agent_max_toolcall_timeout`：默认 120 秒，后端允许 1–3600 的整数秒，前端使用数字输入和加减步进器；统一配置值由版本级配置优先、全局配置次之决定。

## 实施顺序

### 1. 先补充失败测试

- 新增统一超时辅助模块的单元测试：默认值、合法边界、非法配置回退、`min` 合并规则。
- 增加 `RuntimeToolSpec` 普通异步工具超时、同步工具线程边界、异步生成器总时长超时测试。
- 增加 AgentScope 原生工具包装的超时测试，确认原生权限/结果处理仍然保留。
- 增加配置接口校验测试，确认只接受整数秒并拒绝小数、字符串、越界值。
- 增加前端契约测试，确认字段顺序、步进器控件、边界禁用和不存在文本输入框。
- 增加 MySQL/PostgreSQL 迁移静态契约测试，确认新增配置和默认值存在且放在正确版本。

先运行这些聚焦测试，确认它们因功能尚未实现而失败，再进入生产代码修改。

### 2. 实现统一超时策略

- 新增 `app/services/ai/runtime/agentscope/tool_timeout.py`，集中定义默认值、配置范围、配置解析、有效超时计算和批量给 `RuntimeToolSpec` 应用请求级快照的逻辑。
- 在 Assistant、Knowledge、ChatBI 三类运行时工具解析入口读取一次系统配置，构建当前请求的工具快照；不在每次工具调用时重复查询配置。
- 有效超时按以下规则计算：

  `agent_max_toolcall_timeout`（没有版本级覆盖时）

- 未配置或历史非法值回退 120 秒；工具自身未配置超时则继承全局值。

### 3. 接入 AgentScope 工具包装

- 抽取共享调用器，覆盖普通 `RuntimeToolSpec` 和 `AgentScopeNativeApprovalTool`。
- 异步调用使用 `asyncio.wait_for`；同步 legacy callable 使用线程边界执行；异步生成器按整个调用生命周期计时。
- 原生 AgentScope 工具在 schema 支持 `timeout` 时注入/裁剪毫秒参数；显式工具参数不得突破全局上限。
- 超时统一转换为现有 `RuntimeTimeoutError`，写入现有审计/失败证据链，确保 SSE 终态是失败且不产生成功证据；不自动重试。
- 保留原生工具的审批、权限、工具结果与错误语义，并在取消/超时时完成进程或生成器清理。

### 4. 接入配置与数据库

- 在 `app/services/config_service.py` 增加 `agent_max_toolcall_timeout` 的整数范围校验。
- 在系统配置 API 保持通用字符串传输兼容，但保存前严格校验为整数秒。
- 在 `SystemConfig.vue` 的 AI Agent 分组中紧跟 `agent_max_iterations` 展示新配置，使用只读数值和减号/加号按钮，范围 1–3600、步长 1、到边界禁用按钮。
- 新增 `db-prod/V132-add-agent-max-toolcall-timeout.sql` 和 `db-prod-pg/V32-add-agent-max-toolcall-timeout.sql`，不修改既有基线 SQL。

### 5. 验证与收尾

- 先运行新增测试，确认从红转绿。
- 再运行相关后端工具/配置测试、前端契约测试、`vue-tsc --noEmit`（若环境允许）以及 `git diff --check`。
- 进行一次静态执行链复核：普通工具、MCP、ChatBI、原生 Bash/文件工具分别确认经过统一超时入口。
- 请求代码审查，修复审查发现的问题；最终报告代码变更、测试结果和未验证的真实环境边界。
- 不运行 `./dev.sh`，不执行部署或数据库实际变更，不自动暂存/提交。

## 主要文件

- 新增：`app/services/ai/runtime/agentscope/tool_timeout.py`
- 修改：`app/services/ai/runtime/agentscope/tools.py`
- 修改：`app/services/ai/runners/assistant_agent_runner.py`
- 修改：`app/services/ai/runners/knowledge_agent_runner.py`
- 修改：`app/services/ai/runtime/agentscope/data_tools.py`
- 修改：`app/services/config_service.py`
- 修改：`frontend/src/views/SystemConfig.vue`
- 新增：`db-prod/V132-add-agent-max-toolcall-timeout.sql`
- 新增：`db-prod-pg/V32-add-agent-max-toolcall-timeout.sql`
- 新增/修改：相关后端、前端和迁移契约测试

## 风险控制

- 仅在当前请求构建工具时读取配置，避免一次请求中配置热变更造成不同工具使用不同上限。
- 统一包装使用已选定的版本级或全局配置值；HTTP、数据查询、MCP、E2B 和 Bash 内部实现仍可能有独立的基础设施级硬限制。
- 同步工具线程无法被 Python 强制终止，统一包装只能停止等待并记录超时；对可终止的 Bash 子进程继续依赖现有进程组清理。
- 所有验证均区分静态/本地测试证明和真实服务、数据库、Provider 接受情况。
