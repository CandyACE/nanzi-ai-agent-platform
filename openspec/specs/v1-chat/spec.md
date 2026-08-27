# v1-chat Specification

## Purpose
定义 V1 聊天接口的统一响应、异常安全和执行器内部意图分类边界。未指定专家时，接口直接进入默认 `Main` 的智能委派流程；意图分类只用于当前 Main/Executor 的业务处理，不负责在外层选择专家。
## Requirements
### Requirement: 统一执行决策 (Unified Execution Decision)
对外接口 **MUST** 在处理业务逻辑前确定默认 `Main` 或显式指定专家，并由 `TurnDecision` 传递统一执行上下文。需要区分业务类型时，可由对应 Executor 在内部进行意图分类。

#### Scenario: Main 委派数据任务
当外部系统未指定专家并发送“上月 PUE 统计”时，V1 接口应直接进入默认 `Main`；Main 可按需委派数据专家，或由当前执行器完成数据查询分类并触发对应的安全链路，而不是先调用外层语义路由。

### Requirement: 响应结构标准化 (Standardized Response Structure)
所有 V1 对话响应 **MUST** 包含意图标识，以便第三方系统根据意图类型展示不同的 UI 组件（如表格、图表或文本）。

#### Scenario: 外部系统自适应展示
第三方应用通过响应中的 `intent: "DATA_QUERY"` 标识，决定在界面上弹出一个图表弹窗而不是仅仅显示文字。

### Requirement: 异常处理安全性 (Safe Exception Handling)
当 LLM 解析失败或意图不明时，接口 **MUST** 返回友好的降级处理（Fallback），不能暴露后端堆栈信息。

#### Scenario: 模型异常时的优雅提示
当内部网关响应失败时，接口应返回“抱歉，智能体暂时无法解析此请求，请稍后重试”，并保持 HTTP 200 或适当的业务错误码。
