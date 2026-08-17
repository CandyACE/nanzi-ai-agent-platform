# P0 Tool Capability Seam 实施计划

> **For agentic workers:** Execute this plan directly in the current task. Keep unrelated worktree changes intact and do not commit unless explicitly requested.

**Goal:** 统一 AgentScope 运行时工具的定义、解析、权限元数据和 Toolkit 消费入口，同时保持现有工具配置和调用协议不变。

**Architecture:** 在 `app/services/ai/tool_capability.py` 增加 `ToolCapabilityDefinition`、`RegistryToolProvider`、`resolve_tool_capabilities()` 和 `AgentScopeToolConsumer`。三个 AgentScope runner 通过同一 Resolver 获取 specs，仍由现有 `ToolRegistry` 负责实际工具查找和运行时配置覆盖。

**Tech Stack:** Python 3、dataclasses、typing.Protocol、pytest、AgentScope、现有 `RuntimeToolSpec`。

---

## 1. 建立可执行的 seam 契约

**Files:** `tests/ai/test_tool_capability_seam.py`, `app/services/ai/tool_capability.py`

- 先测试 disabled 配置过滤、顺序和同名去重。
- 测试 required tool 缺失报告和 allowlist 对可见/可执行 spec 的共同约束。
- 测试 Definition 复用 source、permission 和抽象 capability 元数据。
- 测试 Consumer 将 Resolver 产出的同一批 specs 原样交给 Toolkit builder。

## 2. 接入三个 AgentScope 工具装配入口

**Files:** `app/services/ai/runners/assistant_agent_runner.py`, `app/services/ai/runners/knowledge_agent_runner.py`, `app/services/ai/runners/chatbi/agent_builder.py`, `app/services/ai/runtime/agentscope/data_tools.py`

- Assistant 和 Knowledge 使用统一 Resolver 合并配置工具与系统隐式工具。
- ChatBI 保持现有默认工具顺序和 required tool 检查，只把解析工作交给统一 Resolver。
- AgentScope Toolkit 通过 Consumer 消费同一份 specs。

## 3. 保持既有配置和回归行为

**Files:** existing focused tests under `tests/ai/runners/`, `tests/ai/runtime/`, `tests/ai/tools/`

- 运行 seam 单测、ChatBI runtime tool 测试、Knowledge/General/Data runner 工具测试。
- 验证结构化 ToolConfigItem 的描述覆盖和数据集范围注入仍生效。
- 不改动普通 legacy Executor 的工具调用路径。

## 4. 文档与检查

- 运行 `pytest` 聚焦测试和 `git diff --check`。
- 若测试暴露既有测试对 Registry 的 patch 依赖，只调整测试接缝，不改变产品配置格式。
- 汇报变更文件、未迁移范围、测试命令和未执行的更大范围检查。

## 5. 第二阶段收口：名称入口与权限诊断

**Files:** `app/services/ai/tool_capability.py`, `app/services/ai/runners/assistant_agent_runner.py`, `tests/ai/test_tool_capability_seam.py`

- 通过 `RegistryToolProvider.get_implicit_tool()` 解析主 General Agent 的 `sub_agent_call`，Runner 不直接调用 Registry 名称查找。
- 为 `ResolvedToolSet` 增加 disabled、filtered、missing 诊断，供后续日志和 UI 使用。
- 在 `ToolCapabilityDefinition` 中标记 `runtime_checked`，只描述权限检查归属，不改变 AgentScope 的实际授权结果。
- 验证 Assistant、Knowledge、ChatBI 和工具 seam 聚焦回归。

## 6. 解析诊断接入执行流和思考卡片

**Files:** `app/services/ai/executors/base.py`, `app/services/ai/runners/assistant_agent_runner.py`, `app/services/ai/runners/knowledge_agent_runner.py`, `app/services/ai/runners/data_agent_runner.py`, `app/services/ai/runtime/agentscope/data_tools.py`, `app/services/ai/runners/chatbi/agent_builder.py`, `frontend/src/utils/processTimeline.ts`, `frontend/src/utils/agentscopeSseHandlers.ts`, `frontend/src/utils/embedThoughtStages.ts`, `frontend/src/utils/turnLogDisplay.ts`, `frontend/src/components/chat/ChatExecutionTimeline.vue`

- 将 `ResolvedToolSet.diagnostics` 转换为安全的 `tool_resolution` 日志事件。
- 在三个 AgentScope 执行入口发送解析诊断；ChatBI required tool 失败时先发送诊断，再保留原有错误事件。
- 复用现有 SSE、消息日志和时间线，把诊断显示在 AI 思考卡片的工具阶段；不改变工具配置、调用参数和运行时权限。
- 增加事件字段安全性和时间线归属测试，并运行聚焦 Python 测试、前端类型检查和差异检查。
