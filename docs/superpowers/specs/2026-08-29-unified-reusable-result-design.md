# 统一可复用结果设计

**日期：** 2026-08-29
**范围：** 后端第一阶段，不新增模型可调用读取工具

## 目标

统一保存普通工具和子代理产生的可交付结果，使下一轮请求可以由服务端按需读取并注入模型上下文，同时保持普通会话历史、子代理会话隔离和现有 ChatBI 逻辑不变。

## 非目标

- 第一阶段不新增 `get_reusable_result` 或 `list_reusable_results` 等模型工具。
- 不改变 `conversation:*:history` 的存储、展示、截断和压缩语义。
- 不做前端展示改造。
- 不新增数据库表或迁移。
- 不迁移已有 Redis 历史数据；通过兼容读取逐步过渡。

## 核心概念

### 会话历史

`conversation:{user_id}:{conversation_id}:history` 是对话事实记录，保存用户消息、助手消息及现有会话事件。它用于展示、审计和一般上下文理解，仍受历史窗口和上下文压缩影响。

### 可复用结果

`reusable_result` 是从工具或子代理输出中提取的派生状态，保存可供下一轮继续分析、总结、改写、导出、可视化或继续处理的结果。它不是历史消息的替代品，也不自动进入每一轮 Prompt。

统一结果至少包含以下字段：

```json
{
  "result_id": "result_xxx",
  "result_type": "data|knowledge|web|file|code|generic",
  "origin_type": "tool|sub_agent",
  "origin_name": "execute_sql_query|data-agent",
  "status": "completed",
  "content": "可读结果或摘要",
  "structured": {},
  "artifacts": [],
  "evidence": [],
  "source": {},
  "trace_id": "trace_xxx",
  "parent_result_id": null,
  "created_at": "2026-08-29T00:00:00+00:00",
  "expires_at": null,
  "freshness": "static|dynamic",
  "requires_fresh": false,
  "reuse_allowed": true
}
```

结果保存前必须完成结果状态判断、敏感信息清理、大小限制和来源元数据补全。失败、超时、取消、权限拒绝、空结果和不可交付的截断结果不得覆盖当前结果。

## Redis Key 设计

规范 key 为：

```text
conversation:{user_id}:{conversation_id}:reusable_result_v1:current
conversation:{user_id}:{conversation_id}:reusable_result_v1:stack
```

- `current` 保存当前最近一个可复用结果。
- `stack` 保存最近若干个可复用结果引用，默认最多 10 个。
- key 始终包含用户和会话边界，禁止跨用户或跨会话读取。
- `current` 在新的成功且可复用结果产生时替换。
- `stack` 追加新结果；相同 `result_id` 幂等更新，不重复追加。
- 普通消息、失败结果和取消结果不覆盖 `current`，也不追加到 `stack`。
- 会话清理时同时删除 `history`、`reusable_result_v1:current` 和 `reusable_result_v1:stack`。

第一阶段沿用 `MemoryService` 默认 TTL 30 天。TTL 从写入时开始计算，读取不自动续期。结果同时支持业务级 `expires_at` 和 `requires_fresh`，因此 Redis 尚未过期不代表结果一定可以继续使用。

## 保存流程

```text
工具/子代理完成
    ↓
规范化为统一结果
    ↓
校验状态、大小、敏感信息、来源和可复用性
    ↓
写入 current，并追加 stack
```

普通工具和子代理使用同一个持久化入口。子代理仍使用独立 `child_session_id`；结果只有在返回主代理后，才由主会话边界提升到主会话的 reusable result，不直接写入主会话。

单轮内可以产生多个候选，但轮末只保存符合策略的最佳候选，避免时钟、检索碎片、纯编排日志和无交付价值的中间结果污染快照。后续阶段可以扩展为按结果类型保存多个 current 指针。

## 读取流程

不新增模型读取工具。每轮模型调用前由服务端的统一 resolver：

1. 按当前用户和会话读取 `current`、必要时读取 `stack`。
2. 根据用户问题识别是否引用旧结果，例如“刚才的结果”“上一个文件”“继续总结”。
3. 检查 `reuse_allowed`、`expires_at`、`requires_fresh` 和结果类型匹配。
4. 选择 current、stack 中的上一个结果或明确 `result_id` 对应结果。
5. 对结果做长度限制和安全格式化。
6. 仅在确实相关时注入统一的 `[可复用结果]` 上下文块。

以下请求不得复用旧结果：

- 明确要求重新查询、最新、刷新、实时数据；
- 当前问题是新的强业务数据请求且旧结果不能证明满足要求；
- 结果过期、权限范围不匹配、类型不匹配或状态不是 `completed`；
- 没有可用结果。

读取逻辑放在公共 Runner 上下文组装边界。DataAgent 可以继续拥有结构化数据快速路径，但底层通过同一个 resolver，并要求 `result_type=data`；普通 Assistant 使用同一 resolver 处理知识、网页、文件、代码和 generic 结果。

## 快捷操作与重复执行控制

通用智能体消息上的“生成可视化分析报告”“保存为 Markdown”“保存为 Word”“提炼生成 Skill”等快捷操作属于对当前回复或当前可复用结果的变换操作，不属于新的数据查询请求。

第一阶段兼容现有前端行为：快捷操作会将用户指令与 `【被点击的 AI 回复】` 及当前回复正文拼接后作为新用户消息发送。服务端识别到该显式上下文标记时，优先将本轮标记为 `reuse_existing_result`：

- 优先读取并使用当前会话中与该回复匹配的 reusable result；
- 有可用且足够的 reusable result 时，不得因为正文中出现“数据、统计、趋势”等词而重新路由到原始查询并再次执行；
- 如果 reusable result 缺失、过期或不足以完成操作，保留现有的正常路由/查询回退逻辑，允许重新调用原工具或子代理；
- 回退执行需要记录本轮未命中/不足的原因，避免把回退结果误认为是直接复用的旧结果；
- 用户明确输入“重新查询、最新、刷新、实时”等意图时，才允许退出复用模式，重新执行数据获取。

ChatBI 已有带 `result_id` 的操作继续使用其专用路径；后续前端增强可以将通用快捷操作的 `source_result_id` 作为结构化请求元数据传入，替代对完整回复正文的依赖，但不作为第一阶段的前置条件。

## 兼容策略

- 新代码优先读取 `reusable_result_v1`。
- 没有新结果时兼容读取现有 `session_tool_artifact_v1`。
- ChatBI 现有 `last_data_result` 和 `data_result_stack_v1` 暂不删除；ChatBI 继续可读写，统一 resolver 可以将其作为 data 类型的兼容来源。
- 不立即迁移或删除旧 key，避免影响现有 ChatBI 追问和黄金报表流程。
- 现有通用快捷操作使用的 `【被点击的 AI 回复】` 文本协议继续兼容，并由服务端识别为复用已有结果的强意图。

## 错误与降级

- Redis 不可用时不阻塞主请求，跳过 reusable result 注入并继续现有流程。
- 结果解析失败时不写入或不覆盖已有结果。
- 结果过大时只保存受限摘要和元数据，并标记 `truncated=true`；不足以安全分析时要求重新调用原工具。
- 结果读取异常时降级为无 reusable result，不把 Redis 异常文本注入模型。
- 用户中断且没有新候选时保留上一份结果；正常轮次结束且没有可复用候选时删除当前通用快照，但不删除结果栈中仍在 TTL 内的历史结果。
- 快捷操作优先复用可用结果；缺少或不足时回退现有查询逻辑，不因统一缓存不可用而改变原有功能。

## 验证范围

第一阶段至少覆盖：

- key 生成包含用户和会话边界；
- 成功工具/子代理结果可写入 current 和 stack；
- 新成功结果覆盖 current，但旧结果仍在 stack；
- 失败、超时、取消和空结果不覆盖旧结果；
- 结果追问会注入，明确刷新请求不会注入；
- 类型、过期时间和 `requires_fresh` 会阻止错误复用；
- 新 key 缺失时可兼容读取旧 `session_tool_artifact`/ChatBI 结果；
- Redis 失败不会阻断主请求；
- 清理会话会删除统一结果 key；
- 现有 ChatBI 和通用工具快照测试保持通过。
