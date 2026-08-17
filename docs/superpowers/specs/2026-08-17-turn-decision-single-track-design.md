# TurnDecision 单轨路由设计

**日期：** 2026-08-17

**状态：** 已实施；旧运行时路由协议已硬切删除

## 目标

将 NanZi 的运行时路由收敛为一套决策模型：`TurnDecision` 是用户本轮请求从路由到执行器之间唯一的运行时决策对象。删除 `RouteResult`、通用 `TurnClassification`、`shared_turn` 和 `route_hints` 在运行时的决策职责，保留 AgentScope、ChatBI 内部分类和现有业务权限判定。

旧 `route_hints`、旧会话恢复数据和旧 replay 格式不需要兼容，也不做历史数据迁移。

## 非目标

- 不重写 AgentScope 的消息流、工具调用、SSE 事件和模型适配层。
- 不删除 ChatBI 的 `DataQueryTurnClassifier`、SQL 修复、结果复用和最终合成链路。
- 不绕过数据集、知识库、工具审批、文件路径和 Grounding 权限校验。
- 不把模型的 reasoning 或用户原文放入公开 trace。
- 不在本次改造中调整前端协议或数据库结构。

## 当前问题

当前请求可能同时经过 `RouterService` 的 `RouteResult`、请求语义 `RequestDecision`、会话级 `TurnClassification`、Dispatcher 的 `shared_turn` 和 Runner 的 `route_hints`。这些对象的字段有重叠，但来源和生命周期不同，导致执行链上存在以下风险：

1. 路由完成后再次调用通用意图分类器。
2. AgentService、Dispatcher 和 ChatBI Runner 对同一请求分别做降级判断。
3. 旧字典提示与结构化对象可能互相覆盖。
4. trace 无法直接回答“最终使用了哪一个决定”。

## 核心设计

### 1. 唯一运行时决策对象

扩展 `TurnDecision`，补齐执行链需要的字段：

- Agent identity：主 Agent、secondary Agent、显式选择来源。
- 路由能力：`source`、`capability`、`turn_kind`、`should_delegate`。
- 语义信息：domain、operation、fact kind、reference mode、relation to previous。
- 数据新鲜度：freshness、time scope、`needs_fresh_data`、最大年龄和来源时间要求。
- ChatBI qualification：mode、evidence level、dataset ids。
- 决策证据：confidence、provenance、fast path、evidence、stage timings。
- 安全结果：`route_status`、`allows_data_route`、`requires_knowledge_search`。

`turn_kind` 取值为 `general`、`knowledge`、`data_query`、`context_action`。它用于日志、Prompt 和 Executor 选择，不再通过另一个通用 `TurnClassification` 推导。

`TurnDecision` 提供两个明确入口：

```python
RouterService.route_query(...) -> TurnDecision
TurnDecision.for_direct_agent_selection(agent_config, ...) -> TurnDecision
```

删除 `from_route_result()`、`to_route_hints()` 和 `from_route_hints()`。`TurnDecision` 不再是旧对象的适配包装，而是路由服务的正式返回类型。

### 2. RouterService 只负责产生决策

`RouterService` 继续负责启发式快捷路径、模型路由、数据路由资格和 secondary agent 选择，但这些结果直接写入 `TurnDecision`。`RouteResult` 从公共返回类型和测试契约中删除。

`RequestDecision` 不再参与 Agent 选择、轮次分类或 Runner 分流。如果现有权限函数仍需要它，只允许在权限边界内从 `TurnDecision` 临时生成一个不可持久化的 authorization view；该 view 不进入 Prompt、trace、Executor 参数或会话状态，也不作为第二套路由决策。

### 3. 单一路由执行流程

```text
用户消息
  ↓
RouterService / direct selection
  ↓
TurnDecision
  ↓
权限与能力校验
  ↓
PromptAssembler(decision)
  ↓
Dispatcher(decision)
  ├─ general      → AssistantExecutor
  ├─ knowledge   → KnowledgeExecutor
  ├─ data_query  → DataQueryExecutor
  └─ context     → 对应上下文动作
```

AgentService 不再执行 `resolve_turn_for_session()`，Dispatcher 不再执行通用分类 fallback。`TurnDecision.turn_kind` 直接决定外层 Executor。

进入 `DataQueryExecutor` 后，ChatBI 可以继续使用自己的 `DataQueryTurnClassifier` 判断新查数、追问、结果复用和可视化动作。这是执行域内部状态机，不回写或替代外层 `TurnDecision`。

### 4. typed decision 取代 route_hints

以下接口从字典改为 typed 参数：

- `AgentService._dispatch_executor(..., turn_decision)`。
- `AgentDispatcher.dispatch(..., turn_decision)`。
- Assistant、Knowledge、Data Runner 构造函数。
- PromptAssembler、tool nudge、grounding、ChatBI handoff 和 repair controller。

需要保存或恢复时，使用 `TurnDecision.model_dump(mode="json")` 作为当前版本的明确状态字段；恢复入口直接校验并重建 `TurnDecision`。不再读取旧的独立语义字段，也不再从普通字典推断路由。

### 5. 权限与 fail-closed

`TurnDecision` 只描述路由意图，不授予权限。所有实际数据、知识库、工具、文件和外部执行权限仍由现有运行时门禁判定。

以下情况必须禁止数据路由：

- `route_status` 为失败或未知。
- `source`/`capability` 不完整且没有显式 Agent 选择。
- 数据路由资格校验失败。
- 当前 Agent 没有对应能力或授权资源。

不能因为某个 Agent 配置了 `data_query` 或 `knowledge_base` 就把失败的路由自动升级为对应执行器。

### 6. Prompt、工具和子代理

- PromptAssembler 直接接收 `TurnDecision`，输出命名 section 和安全决策上下文。
- Tool nudge 直接使用本轮 `TurnDecision` 和工具 metadata，不重新调用请求分类器。
- 工具 metadata 只描述能力、来源、freshness、副作用和确认方式，不改变权限。
- 子代理请求携带父级决策派生的 capability，但仍由现有 readiness、权限、深度、重复调用和 timeout 规则决定是否执行。
- trace 只记录决策版本、来源、能力、turn kind、证据和耗时，不记录模型 reasoning。

## 删除与保留清单

### 删除

- `RouteResult` 及其测试构造方式。
- `TurnClassification` 的通用 General/Knowledge 分流职责。
- `resolve_turn_for_session()`。
- `shared_turn` 参数和会话级分类 tuple。
- `route_hints` 作为运行时输入、输出和恢复协议的职责。
- `TurnDecision` 对旧对象的 route-hints 适配方法。
- 旧 route/replay fixture 和依赖旧字段的测试。

### 保留

- `RouterService`，但它直接返回 `TurnDecision`。
- AgentScope Agent、消息、工具、SSE 和模型运行时。
- ChatBI `DataQueryTurnClassifier` 及 SQL、schema、repair、synthesis 状态机。
- 现有业务权限、数据集授权、知识库绑定、工具审批和 Grounding 门禁。
- `RequestDecision` 的权限层内部临时投影，直到权限 API 可以直接接收 `TurnDecision`。
- Prompt section、tool metadata、ChatBI repair controller 和 subagent protocol。

## 实施顺序

1. 先更新测试契约，验证 `RouterService` 直接返回 `TurnDecision`，并验证未知决策不能进入数据路由。
2. 将 RouterService 的所有快捷路径、模型路径和资格校验迁移到 `TurnDecision`。
3. 删除 AgentService 的通用分类调用，改为直接依据 `turn_kind` 组装 Prompt 和选择 Executor。
4. 删除 Dispatcher 的 `shared_turn`、`turn_decision` fallback 和旧分类分支，只保留唯一 typed decision 输入。
5. 将 Assistant、Knowledge、Data Runner 及 ChatBI handoff 从 `route_hints` 切换到 `TurnDecision`。
6. 将 tool nudge、grounding、subagent 和 trace 调用改为直接读取 `TurnDecision`。
7. 删除旧模型、旧字段、旧 fixtures 和旧测试，增加 forbidden-symbol 静态检查，确保旧链路不会回流。
8. 执行聚焦测试、ChatBI 回归、无基础设施测试、AST 解析和 `git diff --check`。

## 验收标准

- `RouterService.route_query()` 的返回类型只有 `TurnDecision`。
- 生产代码中不存在 `RouteResult`、`shared_turn`、`resolve_turn_for_session` 和运行时 `route_hints` 引用。
- 普通对话、知识库、ChatBI、上下文动作和显式 Agent 选择均只生成一个外层 `TurnDecision`。
- ChatBI 内部分类仍能覆盖新查询、追问、结果复用和 SQL 修复。
- 权限拒绝和未知决策不会被新路由绕过。
- Prompt、tool nudge、subagent 和 trace 使用同一个决策快照。
- 新 replay 测试覆盖所有主要执行分支，且不依赖旧 replay 格式。

## 当前文档入口

- 运行时门控和 Agent 类型约束：`docs/md/ai_agent_gating_contract.md`
- API 路由、自动路由和专家直选说明：`docs/md/api_integration_guide.md`
- 本次实施和验证记录：`docs/superpowers/plans/2026-08-17-turn-decision-single-track.md`

更早日期的方案文档保留为历史记录，其中出现的 `RouteResult`、`route_hints`、`shared_turn` 或通用 `turn_classifier` 只表示当时的实现状态；当前运行时协议以本文和上述三个入口为准。

## 风险与取舍

单轨硬切会扩大一次性改动范围，也会让错误的 `TurnDecision` 影响更多执行路径；因此必须先建立 RouterService、Dispatcher、各 Executor 和权限门禁的契约测试。换取的收益是删除运行时双轨判断，降低重复 LLM、字段漂移和恢复协议分裂的维护成本。
