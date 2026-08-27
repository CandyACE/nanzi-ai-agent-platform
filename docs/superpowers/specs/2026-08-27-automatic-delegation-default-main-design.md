# 自动委派默认 Main 设计

## 背景

当前请求未指定专家时，会进入 `RouterService.route_query()`。该流程需要加载候选智能体、过滤权限、构建资源目录，并可能调用路由模型做意图识别和候选选择。普通请求因此承担了不必要的路由延迟。

平台已有 Main 助手的自动委派能力：Main 可以直接回答，也可以通过 `sub_agent_call` 或 `sub_agent_batch_call` 将知识库、ChatBI 等任务交给可用子智能体。本需求将“自动路由”的产品语义改为“自动委派”：外层不再先判断应该由哪个专家处理，而是统一把请求交给 Main，由 Main 在执行阶段决定是否委派。

## 目标与范围

- 未指定 `agent_id`、`agent_name` 或 `version_id` 时，直接解析默认 Main 智能体。
- 未指定专家的请求全部走 Main，包括携带 `metadata_dataset_ids` 的请求。
- Main 保留直接回答、单智能体委派和批量委派能力。
- 用户明确指定专家、通过 `@专家` 指定专家或指定版本时，保持现有直接选择逻辑不变。
- 删除未指定专家请求对外层 Router LLM 的依赖，缩短首轮执行前等待时间。
- 不删除 `RouterService`，保留其代码和已有测试，供后续兼容场景或显式调用使用。
- 将设置页“自动路由”文案改为“主专家自动委派”，说明默认请求由 Main 直接回答或按需委派其他智能体。
- 将 Main 作为平台固定的主专家：管理页不提供禁用/删除操作，后端也拒绝绕过页面的禁用/删除请求；Main 仍允许配置和发布。
- 普通 EmbedChat 首次加载且用户尚未配置路由偏好时保持 `auto`，不根据允许列表自动填入 Main 的 `expertAgentId`；由后端在无有效专家参数时解析 Main 并生成 `automatic_delegation`。

本需求不改变 Main 内部的委派判定规则、子智能体权限校验、委派深度限制、ChatBI 工具协议、知识库检索逻辑或数据库结构。

## 核心语义

### 四类入口

| 请求入口 | 目标解析 | 决策来源 | 现有逻辑 |
| --- | --- | --- | --- |
| 指定 `agent_id` | 指定智能体 | `direct_agent_selection` | 保持不变 |
| 指定 `agent_name` / `@专家` | 指定智能体 | `direct_agent_selection` | 保持不变 |
| 指定 `version_id` | 指定版本 | `direct_agent_selection` | 保持不变 |
| 无专家参数 | `main`（必要时沿用兼容兜底别名） | `automatic_delegation` | 新逻辑 |

`automatic_delegation` 必须与 `direct_agent_selection` 分开。虽然两者最终都能得到一个已解析的 `ChatConfig`，但 Main 的数据反幻觉 Guard 和自动委派引导依赖“是否显式选择”的语义；把默认 Main 伪装成显式选择会改变现有保护行为。

## 执行链路

### 未指定专家

1. `AgentService` 调用 `AgentContextManager.resolve_agent_config()`。
2. `AgentContextManager` 不调用 `RouterService.route_query()`，优先按 `main` slug 加载启用且有已发布版本的 Main 配置。
3. 如果部署数据仍使用历史通用助手 slug，则按现有兼容兜底顺序查找；数据库没有可用配置时，继续使用现有合成通用配置兜底。
4. 返回 Main 配置和一个 `TurnDecision`：
   - `route_status=resolved`
   - `turn_kind=general`
   - `source=general`
   - `capability=answer`
   - `provenance=automatic_delegation`
   - `fast_path=default_main`
   - `agent_id` / `agent_name` 指向实际解析出的 Main 配置
5. `AgentService` 复用该决策完成上下文重建、提示词组装和 Dispatcher 分发。
6. `AgentDispatcher` 将请求送入 Main 的 AssistantRunner。
7. AssistantRunner 不依赖 Router 的语义字段；它继续基于当前用户问题执行现有 `resolve_request_decision` 和 `tool_nudge_policy`，再结合可用子智能体目录决定是否委派。
8. AssistantRunner 按现有工具引导和模型决策直接回答，或调用 `sub_agent_call` / `sub_agent_batch_call`。

### 显式指定专家

显式 `agent_id`、`agent_name`、`version_id` 及 `@专家` 的参数解析、配置加载、直接决策、权限校验和执行链不做改写。其 `provenance` 仍为 `direct_agent_selection`。

### 数据集范围

`metadata_dataset_ids` 仍由当前请求注入 `AgentContext.metadata_dataset_ids`，但不再触发外层的 `force_data_query` 路径，也不再直接选择 ChatBI 智能体。Main 或其委派工具继续通过当前上下文读取该范围；子智能体执行时沿用现有上下文继承和工具注入机制。

这保证入口统一，同时保留用户明确选定数据集的授权边界。Main 是否委派 ChatBI 由 Main 的现有委派策略决定，而不是由外层 Router 或硬编码数据智能体选择决定。

## 代码改动边界

### `app/services/ai/context_manager.py`

- 将“无显式专家”的分支改为直接解析默认 Main。
- 增加构造默认 Main 自动委派 `TurnDecision` 的内部方法或使用 `TurnDecision` 工厂方法。
- 移除该分支对 `route_query()`、路由进度事件和 `force_data_query` 特殊分流的调用。
- 保留显式 `version_id`、`agent_id`、`agent_name` 分支。
- 保留配置不存在时的安全兜底，但确保 `main` 优先于历史别名。

### `app/services/ai/turn_decision.py`

- 增加默认 Main 自动委派决策的构造方法，或提供明确的参数化工厂方法。
- 保证该决策是 `resolved`，可以被 Dispatcher、Prompt、Runner 和 trace 共同消费。
- 不改变 `for_direct_agent_selection()` 的输出。

### `app/services/ai/agent_service.py`

- 复用 `route_details` 中的默认 Main 决策。
- 仅当决策来源是实际 Router 时发送 `router_log`，避免前端展示虚假的“路由模型已完成”事件。
- 不改变显式专家的 router log/直接选择行为。
- 不再向解析函数传递会导致默认请求强制切 ChatBI 的外层语义；数据集参数仍传入上下文设置链。
- 默认 Main 决策的 `source=general` 允许 AssistantRunner 对当前问题重新执行轻量请求来源/能力判断；该判断不调用 Router LLM，也不选择外层目标智能体。

### `frontend/src/components/embed/ChatSettings.vue`

- 将“自动路由”模式标题改为“主专家自动委派”。
- 将说明改为：未指定专家时，默认由主专家直接回答，或按任务需要自动委派其他智能体，统一流程并减少额外判断耗时。
- 默认专家选择模式保留，显式选择专家的行为不变。

### `frontend/src/views/EmbedChat.vue`

- 普通 EmbedChat 在 `routing_configured=false` 时保持 `routingMode="auto"` 和空 `expertAgentId`，不因允许列表存在 `main` 而切换为专家模式。
- 已保存的专家偏好以及 URL、`INIT_CONFIG`、Ticket 传入的集成锁定专家继续按原逻辑处理。

### `frontend/src/views/AgentManagement.vue`

- 路由帮助、发布确认、配置表单等可见文案统一使用“主专家自动委派”语义。
- 通过 Main 的稳定 ID `sys-agent-chat` 和兼容 slug `main` / `assistant` / `general-chat` 识别固定主专家。
- Main 的状态开关显示为固定启用状态；删除入口、批量禁用选择和单项禁用动作均不可用。

### `app/services/ai/agent_manager.py`

- 在 `update_agent()` 中拒绝将固定主专家设置为禁用。
- 在 `delete_agent()` 中拒绝删除固定主专家。
- 保护以稳定 ID 为主，并兼容历史主专家 slug，防止仅依赖前端隐藏入口。

### 测试

- 新增 ContextManager 单测：无专家时加载 Main，Router 不被调用，返回 `automatic_delegation` 决策。
- 新增数据集范围单测：无专家且带 `metadata_dataset_ids` 时仍解析 Main，并保留当前上下文范围。
- 保留并回归显式 `agent_id`、`agent_name`、`version_id` 的直接选择测试。
- 新增决策工厂单测：默认 Main 与显式专家的 `provenance`、`fast_path` 和能力字段不混淆。
- 新增 AgentService 级别断言：默认 Main 不产生 Router LLM 日志，同时能进入 AssistantRunner 的自动委派能力；显式专家行为不变。
- 新增智能体管理 API 测试：管理员也不能禁用或删除 Main；普通自定义智能体仍可正常更新和删除。
- 更新路由设置文案契约测试：页面使用“主专家自动委派”，不再使用旧的“自动路由”描述。
- 更新智能体管理页面契约测试：Main 不显示状态开关、删除入口和批量禁用目标。
- 运行相关后端定向测试与 `git diff --check`；不启动 `./dev.sh`，不执行部署或生产数据库操作。

## 失败与兼容处理

- Main 被禁用、没有已发布版本或不存在时，沿用现有历史通用助手别名及合成通用配置兜底，避免请求直接失败。
- Router 不再是默认请求的失败兜底，因此默认请求不会因 Router LLM 超时、候选目录异常或路由模型 400 而失败。
- 显式专家配置不存在时，继续沿用现有配置解析和后续错误/兜底行为，不借默认 Main 改写显式选择语义。
- `metadata_dataset_ids` 只影响当前请求上下文和后续工具授权范围，不扩大 Main 或子智能体的数据访问权限。
- Main 的禁用/删除保护在后端执行；前端隐藏操作只是交互层保护，不作为安全边界。

## 非目标

- 不删除或重构 RouterService 的候选、意图识别、路由模型和已有回归测试。
- 不把所有请求改成显式 `agent_id=main`，避免破坏 direct/automatic 语义边界。
- 不修改 Main 的系统提示词、委派提示、委派目标目录和子智能体执行协议。
- 不修改前端专家选择控件的显式选择行为。
- 不禁止编辑 Main 的名称描述、模型、工具和发布版本；本需求只固定其可用性与生命周期存在。
- 不新增数据库字段、迁移或服务启动配置。

## 验收标准

1. 普通无专家请求的执行链中没有 `RouterService.route_query()` 调用或路由模型等待。
2. 普通请求最终执行智能体为 Main，决策来源为 `automatic_delegation`。
3. 普通知识库、ChatBI 或复合任务仍可由 Main 按既有规则委派；直接问答仍由 Main 完成。
4. 带 `metadata_dataset_ids` 的无专家请求仍进入 Main，委派到数据智能体时数据集范围不丢失、不扩大。
5. 指定专家和指定版本的请求与改动前保持相同的配置、决策来源和执行行为。
6. 前端不再把默认 Main 解析伪装成 Router LLM 路由结果。
7. 管理员和普通用户都无法通过页面或接口禁用、删除 Main。
8. 普通 EmbedChat 首次加载默认保持自动委派，不携带 Main 的显式 `agent_id`。
