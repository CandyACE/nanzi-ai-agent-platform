# 会话运行时状态只读工具设计

## 背景

当前 AgentContext 已经保存了智能体、会话、用户、资源范围和模型身份等运行时信息，但这些信息没有统一的只读查询入口。模型在需要判断当前工作目录、设备提示、上下文容量或当前用户身份时，容易依赖猜测，进而产生环境幻觉。

本设计新增一个系统隐式工具 `session_status`，让当前会话中的 AI 按需读取可信的运行时事实。该工具不提供前端页面、不修改会话、不接受外部会话标识参数，也不返回密钥或完整内部状态。

## 目标与非目标

### 目标

- 提供无参数的 `session_status` 工具，范围固定为当前执行上下文。
- 返回会话/Agent 身份、运行时模型摘要、客户端设备提示、用户基础身份、工作区路径、资源范围、附件数量和上下文使用情况。
- 对客户端上报、模型配置、实际 Token 统计和派生路径标明来源或限制，避免把估算值当作事实。
- 通过现有系统隐式工具机制自动提供，并标记为只读工具。
- 复用 AgentScope 工作区解析器，不创建目录、不改变权限、不访问其他用户或会话。

### 非目标

- 不新增前端 UI 或独立状态 API。
- 不提供查询其他会话、其他用户或任意 `conversation_id` 的能力。
- 不返回 API key、base URL、完整 engine_config、完整 AgentState、原始提示词、完整附件绝对路径、完整权限结构或推理内容。
- 不承诺在模型调用尚未完成时提供精确的当前 Token 数和剩余上下文容量。

## 返回契约

工具返回 JSON 字符串，顶层包含 `schema_version` 和 `scope=current_session`。

### session

返回 `conversation_id`、`agent_id`、`agent_name`、可用时的 `agent_type`、可用时的 `trace_id`、当前运行状态和执行阶段。无法从当前 AgentContext 可靠获得的字段使用 `null`，不能猜测。

### client

返回 `device_type` 和 `display_hint`。这两个字段来自请求客户端，必须标记 `source=client_reported`，仅用于回答格式和设备适配判断，不应被描述为服务器检测到的真实硬件事实。

### model

从 `AgentContext.runtime_model_info` 的非敏感字段读取配置模型、生效模型、调用阶段、fallback 状态、上下文窗口、最大输出 Token 和推理开关。只允许显式白名单字段，不能序列化整个 runtime model 对象。

### context_usage

- `last_input_tokens`、`last_output_tokens`、`last_measured_at`：仅在当前上下文已有最近一次可用模型统计时返回。
- `context_window_tokens`：模型配置的上下文窗口。
- `estimated_current_tokens` 和 `estimated_remaining_tokens`：当前没有可靠计算来源时返回 `null`。
- 统计字段为空时返回 `null`，不能使用 `0` 伪装成“已测量为零”。

### user

只返回当前认证上下文中的基础身份：`id`、`user_name`、`real_name`、`role`、`dept_code`、`org_path`、`is_admin`。不接受用户 ID 参数，不调用其他用户查询。详细权限仍由现有 `get_myinfo` 工具负责。

### workspace

使用 `app.services.ai.runtime.agentscope.workspace` 的解析函数计算当前实际运行时根目录，并返回：

- 用户工作区根目录；
- 当前会话工作目录；
- 跨会话默认文档目录；
- 用户上传目录；
- SQLite 临时沙箱目录。

每个目录返回 `path`、`exists`，目录存在时返回 `writable`。读取状态不得创建目录。路径只在当前用户工作区边界内生成。

### resources 与 attachments

资源返回当前 AgentContext 中已经生效的数据集、知识库数据集、MetaDataset 和技能；MCP 工具名称只有在当前上下文可靠保存时才返回，否则为 `null` 并说明不可用。附件只返回授权附件数量、当前轮附件数量和文件名，不返回完整授权绝对路径列表。

### limitations

返回影响解释的已知限制，例如设备字段是客户端上报、Token 是最近一次已完成调用的统计、当前 Token 估算不可用等。限制文本是固定后端文案，不由用户参数拼接。

## 安全与只读边界

- 工具签名不接收参数，始终从 `get_current_agent_context()` 和当前请求 debug context 读取信息。
- 工具不调用写入接口、不创建目录、不修改 Redis、数据库、AgentState 或会话资源范围。
- `api_key`、`base_url`、`engine_config`、`rag_params`、`permission_options`、`event_queue`、`grounding_evidence_ledger` 和原始附件路径不进入结果。
- 工具加入 `SYSTEM_IMPLICIT_TOOLS`，并加入 `READ_ONLY_TOOL_NAMES`，运行时权限为 `read`。
- 工具声明 `RUNTIME_STATE` 取证类型，使模型可以把它当作当前运行环境事实来源。

## 实现边界

- 新建 `app/services/ai/tools/session_status.py`，负责快照组装、字段白名单、路径状态和 JSON 序列化。
- 修改 `app/services/ai/tools/registry.py`，注册静态工具并加入系统隐式工具。
- 修改 `app/services/ai/runtime/agentscope/tools.py`，声明只读工具名称。
- 修改 `app/services/ai/tools/registry.py` 的 `TOOL_EVIDENCE_TYPES`，将工具映射为 `RUNTIME_STATE`。
- 修改系统工具注入契约测试，并新增针对快照脱敏、路径解析、设备来源、上下文统计和无参数调用的单元测试。

## 验证

- 先运行新增测试，确认在实现前因工具不存在或字段缺失而失败。
- 实现后运行新增工具测试、系统工具注入测试、运行时只读权限测试和工具证据测试。
- 运行 `git diff --check`，确认不涉及服务启动、数据库迁移或前端构建。
