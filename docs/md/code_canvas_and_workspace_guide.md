# 代码画布与工作区执行指南

代码画布用于在当前会话中查看、运行和解释短小的 Python 或 Shell 代码。它是用户可控的工作区能力，不等同于安装任意系统工具，也不会绕过 Agent、MCP、Skill 或 RBAC 权限。

## 适用场景

- 在 ChatCanvas 中临时验证数据处理、文件整理或计算逻辑；
- 将运行输出继续交给当前对话分析；
- 打开工作区中的 `.py`、`.sh`、`.bash` 文件，确认内容后执行。

当前支持的语言为 `python`、`sh`、`bash`；`python3` 和 `shell` 作为兼容别名。Node.js、JavaScript、TypeScript、SQL 不是代码画布的执行语言。

## 在界面中使用

1. 在对话中打开代码画布，或从工作区预览中打开脚本。
2. 编辑代码并点击运行。画布会在成功打开后固定到当前会话，用户也可以手动取消固定。
3. 运行期间可查看 stdout、stderr 和状态；需要提前结束时点击停止。
4. 运行结束后，可将结果发送回对话，让智能体继续解释或生成下一步操作。

保存文件和运行文件是两个独立动作：只保存不会执行，运行时应以当前画布内容或明确选中的工作区文件为准。

## V1 API

所有接口都需要 API Key。流式执行：

```http
POST /api/v1/chat/code-executions/stream
Content-Type: application/json
Authorization: Bearer <api-key>
```

请求体：

```json
{
  "language": "python",
  "code": "print('hello')",
  "conversation_id": "conversation-id"
}
```

响应为 SSE。事件的 `data` 是 JSON，常见事件包括执行状态、stdout、stderr 和完成结果；状态可能为 `succeeded`、`failed`、`stopped`、`timed_out` 或 `blocked`。

停止执行：

```http
POST /api/v1/chat/code-executions/{execution_id}/stop
Content-Type: application/json
Authorization: Bearer <api-key>
```

```json
{
  "conversation_id": "conversation-id"
}
```

接口详情和通用流式约定见 [API 集成指南](api_integration_guide.md)。

## 执行边界

- 每个用户/会话使用隔离的私有工作区，不能通过路径穿越访问其他工作区；
- 只调用平台允许的固定解释器，不提供 Node、包管理器或任意命令安装入口；
- 默认单次执行超时为 60 秒，输出上限为 100 KB，超限或超时会结束本次执行；
- 停止操作必须匹配当前用户和会话，不能停止其他用户的执行；
- 工作区文件执行仍需通过路径安全校验，悬空符号链接和解析后越界路径会被拒绝；
- 代码画布不改变数据库、MCP Server、Skill 发布或 Agent 工具白名单的权限边界。

生产环境如需调整超时、输出上限或工作区策略，应以当前服务配置和安全评审为准，不要在前端绕过限制。
