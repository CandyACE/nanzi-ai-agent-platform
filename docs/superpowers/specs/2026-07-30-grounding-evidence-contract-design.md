# Grounding 证据契约与路由冲突治理设计

## 背景

当前请求路由同时产出 request_source、request_capability、semantic_domain、fact_kind 和时效字段。grounding 层再从这些字段分别推断证据类型：来源、语义域或事实类型任一字段命中，就可能把本轮回答标记为必须取证。

这会造成三类问题：

- 路由来源为 unknown，但语义域带有 public_web 或 public_fact，最终仍被要求公网凭证。
- LLM 路由提示覆盖了本地确定性边界，例如日期时间、普通解释和文本处理。
- 用户看到“证据凭证缺失”，但无法知道到底是谁要求了证据、要求哪一类证据，以及字段之间是否冲突。

## 目标

1. 将“请求来源分类”和“是否需要证据”解耦为明确的证据契约。
2. 对 unknown 请求采用宽松默认：没有明确来源或高置信高风险语义时，不强制取证、不弹高风险提示。
3. 保留对高置信内部业务数据、运行状态、知识库、公网查询和用户显式取证要求的保护。
4. 确定性边界优先于弱路由元数据，避免普通通用回答被错误升级。
5. 记录决策来源、置信度和冲突，支持定位线上误报。

## 非目标

- 不重写 RouterService 的智能体选择算法。
- 不改变工具执行权限、审批或 AgentScope 工具循环策略。
- 不让前端静默隐藏后端 grounding 决策。
- 不改变用户显式 retry/method grounding 操作的优先级。

## 设计

### 1. 证据契约

在 app/services/ai/grounding/contract.py 增加稳定的数据边界：

    EvidenceContract
      mode: none | optional | required
      accepted_types: EvidenceType 集合
      origin: explicit | lexical | semantic | router | fallback
      confidence: float
      reason: str
      conflicts: tuple[str, ...]

GroundingService 和 resolve_fact_requirement 只消费规范化后的契约/需求，不再直接将任意原始字段视为强制证据。

### 2. 决策优先级

证据契约按以下优先级生成：

1. 用户显式来源要求（联网查、查本机、查知识库、查业务数据）进入 required。
2. 确定性词法边界（日期时间、问候、代码解释、文本处理、平台帮助）进入 none。
3. 高置信且互相一致的语义域、事实类型和时效要求进入 required。
4. 对话结果复用进入复用模式，不因旧结果重复要求新证据。
5. unknown 或字段冲突默认进入 optional，不产生强制证据要求；如果本轮仍无法分类且回答包含结构化/高风险事实，再交给现有未知事实护栏。

unknown + semantic_domain=public_web 这类组合不再自动升级为公网取证；explicit public_web 仍然可以覆盖弱语义冲突。普通日期、问候和其他确定性 general 边界会在 runner 中先被重新归类为 none。

### 3. 与现有 FactRequirement 的关系

保留现有 FactRequirement 作为 grounding 执行输入，增加契约来源和冲突元数据，或由契约集中转换为 FactRequirement。required 只能来自 EvidenceContract.mode=required，不能由单独的 domain/fact_kind 字段隐式触发。

用户主动发起的 retry/method action 仍在 runner 层优先处理，作为显式操作覆盖普通自动决策。

### 4. 可观测性

路由日志和 grounding 调试元数据增加：

- decision_origin
- decision_confidence
- evidence_mode
- accepted_evidence_types
- decision_conflicts

用户可见文案保持现有简洁提示；详细决策只进入日志/结构化 SSE 调试字段。

## 数据流

    用户问题
      -> RouterService / TurnClassifier
      -> AssistantAgentRunner 规范化请求决策
      -> EvidenceContract
      -> FactRequirement
      -> EvidenceLedger + GroundingService
      -> 正常回答 / 来源提示 / 风险提示

## 错误与兼容行为

- 缺少路由元数据时，使用当前轮确定性规则重新推断。
- unknown 不再因为动态日期、时间等确定性通用问题进入未知事实审查；仍无法分类的结构化/高风险事实继续使用可选的未知事实护栏。
- 明确业务数据、运行状态、公网或知识库请求没有凭证时，仍保留现有 warning/block 语义。
- 字段冲突不丢失：记录冲突原因，但不把低可信冲突直接变成高风险用户提示。
- 旧调用方仍可使用 resolve_fact_requirement，避免一次性改动所有 runner。

## 测试策略

先写失败测试，再实现：

1. unknown + 今天日期不产生 evidence requirement 或 warning。
2. unknown + semantic_domain=public_web 不强制公网凭证，但记录冲突。
3. 明确公网、内部数据、运行状态和知识库请求无凭证时仍提示缺失证据。
4. 相同请求有匹配工具凭证时正常通过。
5. 高风险内部业务表格回答继续触发业务幻觉护栏。
6. retry/method action 仍覆盖普通自动决策。
7. 全部现有 grounding、request decision、turn classifier 回归测试保持通过。

## 验收标准

- 普通 general/answer 和无法可靠分类的普通动态事实不再出现高风险来源提示。
- 所有强制证据提示都能从结构化字段看出证据类型和决策来源。
- 明确的数据、知识、公网和运行状态保护不被削弱。
- 只运行定向测试和必要静态检查，不启动 ./dev.sh。
