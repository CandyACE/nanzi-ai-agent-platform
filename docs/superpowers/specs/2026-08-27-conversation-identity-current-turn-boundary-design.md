# 会话身份隔离与当前轮边界设计

## 背景

本次问题有两个相互独立但会同时放大风险的缺口：

1. Redis 主历史使用用户 ID 和会话 ID，但缺少用户身份时会降级为 `anonymous`；Redis 为空时的数据库历史回退主要按 `conversation_id` 和用户名过滤，未形成全链路一致的用户归属校验。
2. 服务端已经把历史消息和当前消息放在同一组模型消息中，并通过提示词说明最后一条 user 是当前请求，但执行器仍允许模型根据历史 assistant 内容、隐藏工具摘要或工具说明自行发起本轮工具调用。当前轮边界依赖提示词，缺少执行层约束。

用户在当前会话中只输入“你好”，可见历史全部为 ChatBI 查询；系统却执行了 `list_process` 和 Bash。修复必须解决通用的“当前输入与历史背景混淆”，不能针对某个问候词添加特例。

## 目标

- 所有会话历史、上下文摘要、会话资源范围、截断和删除操作都要求真实用户身份与 `conversation_id`。
- 缺少用户身份时 fail closed，返回认证错误或服务层身份错误，不再生成或使用 `anonymous` 会话空间。
- 数据库历史回退必须按 `AgentExecutionHistory.user_id` 校验归属；旧记录没有 `user_id` 时不以用户名猜测归属。
- 路由和执行器都显式区分 `current_user_message` 与 `conversation_history`。
- 历史消息只作为背景、指代和结果证据；历史用户问题、assistant 指令、旧工具计划和旧工具结果不能单独触发当前轮工具。
- 当前输入明确提出任务时，保留现有 ChatBI、知识库、文件、网络和运行时工具能力；当前输入只是普通聊天时，不因历史工具或工具描述启动工具循环。
- 保留合法的当前轮追问，例如“继续分析上面的结果”，但该继承必须由当前输入的追问语义和当前轮路由决策共同确认。

## 非目标

- 不删除会话历史，不强制把每次对话变成新会话。
- 不清空 ChatBI 结果栈、摘要或历史展示；它们仍受同一用户和会话身份保护。
- 不改变工具本身的执行权限、沙箱后端和危险命令拦截策略。
- 不用单纯扩大或缩小上下文 token 预算解决当前轮混淆。
- 不把所有历史从模型中删除；合法追问仍需要历史背景。

## 方案对比

### 方案 A：只加强系统提示词

改写“历史仅背景”的提示词，不增加执行层检查。改动小，但无法阻止模型在长上下文中误调用工具，也无法修复用户身份缺失和数据库回退隔离问题。不采用。

### 方案 B：丢弃历史，只发送当前消息

可以避免历史诱发工具，但会破坏 ChatBI 追问、上下文引用和会话连续性。不采用。

### 方案 C：结构化当前轮 + fail-closed 身份校验 + 执行器工具门禁

路由继续使用完整的服务端历史，执行器把历史作为明确的背景区，并把当前消息作为唯一当前请求；工具执行前根据当前轮决策和当前输入判断是否允许调用。会话存储层统一拒绝缺失身份，数据库回退按 `user_id` 过滤。该方案保留已有连续对话能力，同时把正确性和安全边界从提示词提升到代码层，作为本次实现方案。

## 架构与数据流

```text
HTTP auth
  -> required_user_id(user_info)
  -> required conversation ownership scope
  -> Redis key: conversation:{user_id}:{conversation_id}:...
  -> server history + current_user_message
  -> router uses current input plus history as background
  -> executor builds explicit current-turn context
  -> current-turn tool gate
  -> tool wrapper / AgentScope execution
```

### 身份隔离

新增共享的必需用户身份解析入口，统一接受认证结果中的 `user_id` 或兼容字段 `id`，转换失败或缺失时抛出明确的身份错误。会话相关 API 在进入 Redis、数据库、资源范围和执行锁之前调用该入口。

`MemoryService` 和 `ConversationResourceService` 的 key 构造不再把空值转换成 `anonymous`。底层服务对缺失身份直接失败，避免任何调用方绕过 API 层产生公共 key。普通聊天历史的 Redis 读取仍按 `conversation:{user_id}:{conversation_id}` 进行。

历史 API 的 Redis 为空时，数据库回退查询必须同时满足：

```text
AgentExecutionHistory.conversation_id == requested_conversation_id
AgentExecutionHistory.user_id == current_user_id
```

不再用 `username` 作为用户归属替代。`user_id` 为空的遗留记录不返回给普通用户。管理员如需查看其他用户记录，必须走已有明确的管理权限入口，不得因为普通会话历史接口的 URL 带有会话 ID 就自动放宽归属检查。

### 当前轮边界

服务端在历史读取后保留明确的 `current_user_message`，不要让执行器通过扫描消息列表猜测当前问题。路由可以继续读取历史中的上一轮 agent、摘要和指代信息，但其 `TurnDecision` 必须记录本轮输入对应的语义。

执行器上下文按以下顺序构造：

1. 平台 system prompt 和本轮路由快照；
2. 一个明确标记为“历史背景、不可直接执行”的历史区，保留必要的历史 user/assistant 内容和工具结果摘要；
3. 一个明确标记的当前用户请求；该请求是本轮唯一任务来源。

当前输入若明确引用历史结果，路由决策可以把关系标记为 `followup` 或允许的 `resume_topic`，并允许对应能力继续工作。仅因为历史中出现过某个工具、某个 Agent 或未完成建议，不得获得当前轮执行资格。

### 当前轮工具门禁

工具集合仍由 Agent 发布配置和权限系统决定；新增的是本轮调用资格判断。门禁接收当前用户文本、`TurnDecision`、工具元数据和必要的历史关系标签：

- 当前轮为结构化业务查询且决策允许数据路由时，才允许 ChatBI 数据工具；
- 当前轮明确要求知识检索、文件、网络、运行时状态或操作时，才允许对应工具；
- 当前轮是普通聊天或普通问候时，历史中的工具调用记录不能启动工具循环；
- 当前轮为明确历史结果追问时，只允许与该追问能力匹配的工具；
- 被门禁拒绝的模型工具调用不执行，不弹出执行确认卡；向模型注入当前轮边界错误，允许它无工具重新回答。

该门禁不替代危险操作确认和用户权限校验，只负责阻止“历史诱发的无关工具调用”。

## 错误处理

- 认证结果无有效用户 ID：HTTP 401，错误信息为无法识别当前用户；不访问或写入任何会话 key。
- 当前用户访问其他用户的会话 ID：Redis 只命中当前用户分区；数据库回退无匹配时返回空历史或 403，不能跨用户回退。
- 历史记录 `user_id` 为空：严格用户查询不返回该记录；不根据用户名自动认领。
- 当前轮工具调用与 `TurnDecision`/当前输入不匹配：不执行、不创建确认请求，产生可观测的拒绝事件并让模型按当前请求重新回答。
- 合法的 ChatBI 追问、明确的历史恢复和显式用户操作保持现有流程，不因历史区封装而丢失必要上下文。

## 测试与验收

后端测试覆盖：

- `MemoryService`、`ConversationResourceService` 缺失用户 ID 时失败，不生成 `anonymous` key；
- Redis 历史按用户 ID 和会话 ID隔离；不同用户使用相同会话 ID 不能互读；
- DB 历史回退使用 `user_id`，不使用仅用户名匹配，不返回 `user_id IS NULL` 的记录；
- 当前输入为普通聊天、历史包含 ChatBI 或运行时工具时，工具调用为零；
- 当前输入为新的 ChatBI 查询、运行时诊断或文件任务时，仍允许匹配的工具；
- 当前输入“继续分析上面的结果”等明确追问时，允许对应历史结果能力，不允许无关工具；
- 当前轮工具门禁拒绝时不创建权限确认卡；
- AgentScope 状态恢复、配置变更重置和普通历史窗口仍保持当前轮消息正确。

前端契约测试确认普通发送只提交当前 user 消息，UI 的“以上是历史会话”分隔符不进入执行请求；编辑重发仍先显式截断再发送。

验证范围包括聚焦 pytest、前端契约测试、Python 编译、`git diff --check`，不启动 `./dev.sh`，不执行部署或生产数据库操作。

## 影响文件

- `app/services/ai/memory_service.py`：移除匿名 key 降级，统一必需用户身份。
- `app/services/conversation_resource_service.py`：移除匿名资源范围 key 降级。
- `app/core/dependencies.py` 或会话访问辅助模块：提供必需用户身份/会话归属校验。
- `app/api/v1/endpoints/chat.py`：历史、上下文、资源范围、截断、删除和恢复入口使用严格身份校验；DB 回退按 `user_id` 查询。
- `app/services/ai/agent_service.py`、`app/services/ai/runners/assistant_agent_runner.py`：传递显式当前轮上下文，并接入工具门禁。
- `app/services/ai/executors/common.py`：提供历史背景与当前用户消息的结构化转换。
- `app/services/ai/audit.py`：确保新写入审计记录使用规范化用户 ID。
- `tests/services/ai/`、`tests/api/`、`tests/ai/runners/`、`tests/frontend/`：覆盖身份隔离、当前轮边界和工具调用资格。
