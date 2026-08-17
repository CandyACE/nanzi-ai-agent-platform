# P0 Tool Capability Seam 设计

## 目标

把工具的解析、能力元数据和 AgentScope 工具组装拆成明确的 Definition、Provider、Resolver、Consumer 角色，让“模型可见工具”和“实际可执行工具”来自同一份解析结果。

## 保持不变的外部行为

- 智能体版本中的 `tools` 仍支持字符串、`ToolConfigItem` 和数据库字典配置。
- 现有工具名称、参数 schema、`metadata_dataset_ids`、MCP 可见性和工具调用结果保持不变。
- `ToolRegistry.get_tool()`、`get_tools()` 和 `get_runtime_tools()` 继续保留，作为已有调用方的兼容入口。
- ChatBI 仍使用现有 SQL Loop；本次只统一 ChatBI 的工具解析和 AgentScope Toolkit 消费入口。

## 运行时分层

1. `ToolCapabilityDefinition` 描述工具名称、来源、权限范围和抽象能力元数据，不执行工具。
2. `RegistryToolProvider` 复用现有 `ToolRegistry`，负责从静态注册表、ChatBI 特殊工具、MCP 和 HTTP/API 工具取得 `RuntimeToolSpec`。
3. `resolve_tool_capabilities()` 负责配置启用状态、顺序、去重、必需工具和子代理 allowlist，并产出唯一的 `ResolvedToolSet`。
4. `AgentScopeToolConsumer` 只消费 `ResolvedToolSet.specs` 构造 AgentScope Toolkit，不再自行重新解析工具。

## 关键规则

- `enabled=False` 的配置项不进入本轮模型可见或可执行列表。
- 配置顺序优先；必需工具在配置工具之后补齐；系统隐式工具最后补齐；同名工具只保留第一次出现的 spec。
- `allowed_names` 在所有来源合并后统一应用，因此工具可见性和执行权限使用同一份 allowlist。
- 必需工具缺失不静默忽略，返回 `missing_required`，由 ChatBI 入口继续抛出原有 `RuntimeConfigurationError`。
- Definition 的抽象元数据复用现有 `resolve_tool_metadata()`，不把元数据解析变成新的权限授予机制；真正的执行权限仍由 `RuntimeToolSpec` 和 AgentScope permission hook 执行。

## 本阶段边界

本阶段接入 Assistant、Knowledge 和 ChatBI 三个 AgentScope 工具装配入口。普通旧 Executor、工具管理 API 和 ChatBI SQL 执行状态机暂不迁移，避免扩大行为变更面；它们可以在后续阶段通过同一个 Provider 迁移。

## 第二阶段收口

第二阶段把主 General Agent 获取 `sub_agent_call` 的名称查找也放入 `RegistryToolProvider`，Runner 不再直接访问 `ToolRegistry.get_tool()`。

`ResolvedToolSet` 增加静态解析诊断，记录配置禁用、allowlist 过滤和 required tool 缺失。`ToolCapabilityDefinition.execution_policy` 固定为 `runtime_checked`，表示最终权限仍由 AgentScope runtime tool 的 permission hook、用户禁用工具策略、命令黑名单和确认模式决定；Resolver 不会在组装阶段替代这些动态检查，也不会因为能力元数据而自动放行工具。

## 解析诊断可观测性

执行器在完成本轮工具解析后，将诊断转换为增量 `type=log` 事件，`category=tool_resolution`。事件只包含工具名、`disabled`/`filtered`/`missing` 状态和安全原因，不包含工具参数、可执行对象、凭据或权限明细。

Assistant、Knowledge 和 ChatBI 的正常执行流都会发送这些事件；ChatBI 的 required tool 解析失败也会先发送诊断，再发送原有错误事件。前端复用现有 SSE 日志链，将事件写入 `msg.logs` 和 `processTimeline`，并在思考卡片的“执行工具”阶段显示。该事件为附加观测信息，不改变工具列表、调用参数、运行时权限检查或失败语义。
