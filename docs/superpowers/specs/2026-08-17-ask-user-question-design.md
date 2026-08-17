# `ask_user_question` 交互式提问设计

## 目标

为主助手、ChatBI 和知识库助手增加一种由 AI 主动发起的澄清交互：当执行缺少会实质改变结果的条件，或存在多个同等合理分支时，AI 调用 `ask_user_question` 展示单选、多选或补充输入卡片；用户提交后以同一 `conversation_id` 开始新一轮执行。

本能力与 `request_user_confirmation` 保持独立。业务确认用于执行写入前确认已形成的字段；用户提问用于补齐分析条件或选择后续执行分支。

## 范围

本期包含：

- 全局隐式工具 `ask_user_question`，通过现有 Tool Capability Seam 同时进入模型可见工具和实际 Runtime Tool。
- 单选、多选、可选自定义输入和问题背景说明。
- `awaiting_user` pending 状态、SSE `user_question` 事件、Redis TTL、用户归属校验、选项校验和重复提交幂等。
- EmbedChat 与 AgentDebug 的独立提问卡片。
- 用户回答以结构化回执进入同一会话的新一轮模型执行，并保持上一智能体/ChatBI/知识库路由粘性。
- 提问事件、用户回答和最终结果随父会话历史/执行轨迹保存。

本期不包含：

- 子代理等待用户后恢复；子代理触发提问时先返回明确的未支持状态，不伪装成已完成。
- 恢复原始 Python/AgentScope 协程或模型调用现场；用户回答采用新一轮消息继续。
- 独立的提问会话列表或独立聊天窗口。
- 路由器在未选出智能体前的专用澄清流程；本期提问发生在已选智能体执行期间。

## 与业务确认的边界

| 项目 | `request_user_confirmation` | `ask_user_question` |
| --- | --- | --- |
| 目的 | 确认即将执行的业务动作 | 补齐缺失条件或选择分析分支 |
| 典型内容 | 录入供应商前确认字段 | 按天还是按月统计 |
| 结果 | 确定或取消 | 选项 ID 列表和自定义补充 |
| 后续动作 | 可能调用写入工具 | 继续查询、检索或分析 |
| 前端组件 | 业务确认卡 | 用户提问卡 |
| 回执前缀 | `【业务确认】` | `【用户回答】` |

两者共享 pending 生命周期、SSE 传输和历史记录的基础机制，但不共享业务 payload、Prompt 规则或前端组件。

## 协议

工具参数：

```python
class QuestionOption(BaseModel):
    id: str
    label: str
    description: str | None = None

class AskUserQuestionArgs(BaseModel):
    question: str
    options: list[QuestionOption]
    is_multi_select: bool = False
    allow_custom_input: bool = True
    context: str | None = None
```

服务端生成 `question_id`，并返回：

```json
{
  "status": "awaiting_user",
  "interaction_type": "question",
  "question_id": "uq_xxx",
  "question": "希望按哪个时间维度统计？",
  "options": [
    {"id": "daily", "label": "按天"},
    {"id": "monthly", "label": "按月"}
  ],
  "is_multi_select": false,
  "allow_custom_input": true,
  "context": "当前数据集包含过去一年的交易数据"
}
```

服务端验证规则：问题非空，选项至少两项，选项 ID 非空且唯一，选项数量和文本长度有上限；多选和自定义输入按参数执行。资源类选项仍必须属于当前用户可访问范围，不能仅信任模型生成的 label。

用户回答回执：

```text
【用户回答】
interaction_type: question
question_id: uq_xxx
selected_option_ids: ["monthly"]
custom_input: 排除退款订单
```

用户点击取消时，回执增加 `cancelled: true`，选项和补充输入为空。服务端将 pending 记录置为 `cancelled`，清理活动问题标记，并返回已取消状态；同一问题的重复提交保持幂等，不会覆盖取消结果。

前端回执中的 `question_id`、选项 ID 和会话归属在服务端根据 pending 原始记录重新校验；不接受任意用户手工伪造的选项作为有效回答。

## 执行和状态

工具调用成功后，当前执行循环必须识别 `status=awaiting_user`，停止后续模型和工具调用，并发送 `user_question` SSE 事件。系统将 pending 记录写入 Redis，键包含用户和会话范围，状态为 `pending`，默认设置有限 TTL。

用户提交后，服务端原子地将 pending 状态变为 `submitted`，重复提交返回同一个处理结果；过期问题变为 `expired`，不能继续执行。回答内容作为同一会话的新一轮用户消息交给上一轮选中的智能体。业务路由层通过 `question_id` 回执识别并沿用上一智能体，避免重新把回答误路由到通用助手或公网搜索。

用户取消后，服务端不再进入路由、模型或工具执行，直接在同一会话写入简短的取消结果；提问卡变为只读的“已取消”状态。

同一会话只允许一个活动提问卡。已有 pending 时，新的 `ask_user_question` 调用返回明确错误并停止重复弹卡。

## UI 和历史

EmbedChat 与 AgentDebug 在当前 AI 消息下渲染 `UserQuestionCard`，展示问题、背景、选项和补充输入。提交或取消后卡片只读展示结果；过期或异常显示不可提交状态。

SSE 断线或页面刷新后，通过当前消息的历史快照和 pending 查询恢复卡片。主会话仍只有一条用户会话，不新增子会话；提问事件、回执和最终回答写入同一会话的过程轨迹/消息历史。

## 提示词规则

仅当缺失条件会实质改变查询结果、存在多个同等合理分支，或用户明确要求 AI 先询问时，才调用 `ask_user_question`。能够依据上下文安全推断的默认项不应反复询问。

每轮最多发起一个问题。调用后必须停止并等待 `【用户回答】`；收到回答后根据选项 ID 和补充输入继续，不得重复询问同一问题，除非用户提供了新的任务或明确要求修改答案。

## 测试验收

- 参数校验拒绝空问题、少于两项、重复选项 ID 和超长 payload。
- 工具返回 `awaiting_user`，并且执行循环不会继续产生模型/工具调用。
- `user_question` SSE payload 与前端解析字段一致。
- pending 记录按用户、会话和 question ID 隔离，过期、重复提交和跨用户提交均被拒绝。
- 单选、多选、自定义输入的合法/非法回执均有覆盖。
- 用户回答继续同一会话并保持上一智能体路由粘性。
- EmbedChat、AgentDebug 的卡片渲染、提交、只读和过期状态有契约测试。
- 现有业务确认卡、工具权限、子代理委派和 ChatBI 回归测试保持通过。
