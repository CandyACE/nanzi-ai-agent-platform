# 统一 Agent 超时配置设计

**日期：** 2026-08-31

## 目标

让子代理整体委派超时和聊天页面的挂起步骤提示统一使用系统配置
`agent_max_toolcall_timeout`，消除后端实际超时与前端默认提示不一致的问题。

## 当前问题

- `sub_agent_call` 此前使用独立的 `sub_agent_delegation_timeout_seconds`，默认 120 秒。
- `markStalePendingStreamLogs` 此前在前端固定使用 `120_000` 毫秒。
- 两处数值虽然当前都为 120，但配置来源不同；管理员修改
  `agent_max_toolcall_timeout` 后，前端提示和子代理整体委派仍可能不同步。
- 前端聊天用户没有直接读取系统配置的通用权限入口，单独增加配置请求会产生权限和时序不一致问题。

## 设计方案

### 配置来源

后端继续使用既有的 `load_agent_max_toolcall_timeout()` 读取
`agent_max_toolcall_timeout`。该读取使用默认 180 秒、合法范围和 Redis/数据库回退行为。

`sub_agent_delegation_timeout_seconds` 不再作为子代理整体委派的运行时来源；为兼容已有部署，暂不删除该历史配置键，但代码不再读取它。

### 后端子代理调用

`sub_agent_call` 在构造 `SubAgentRequest` 和包裹子代理流的
`asyncio.wait_for` 时，均使用 `load_agent_max_toolcall_timeout()` 得到的全局超时快照。

`sub_agent_batch_call` 继续复用 `sub_agent_call`，因此每个批量子任务使用同一配置值独立计时；批量工具本身不新增另一层固定总超时。

超时后的行为保持不变：返回 `TIMEOUT` 结果、写入停止原因，并关闭异步子代理流释放资源。

### 前端看门狗

流式聊天开始时，由后端下发本次运行的超时配置快照，例如：

```json
{
  "type": "run_config",
  "agent_max_toolcall_timeout": 300
}
```

前端将该值保存到当前消息，`markStalePendingStreamLogs` 优先使用消息快照换算毫秒。这样同一轮前端提示使用的就是后端本次运行读取的配置。

如果历史消息、旧服务端或异常流没有携带快照，前端保留 180 秒兼容兜底；该兜底只用于兼容显示，不改变后端任务执行，也不再作为正常新请求的配置来源。

看门狗仍然只负责将超过阈值的 pending 日志标记为错误并结束前端思考态，不负责取消后端任务。后端任务是否结束仍由后端运行链路和现有取消机制决定。

### SSE 事件处理

新增的 `run_config` 事件由共用的 SSE 事件处理器消费，`EmbedChat` 与 `AgentDebug` 不各自实现解析逻辑。未知或缺少该事件时保持现有事件流兼容。

## 错误处理与边界

- 后端配置读取失败或配置非法时，复用既有解析逻辑的安全默认值 180 秒。
- 前端收到非正数、非有限数或缺少字段时，忽略该快照并使用 180 秒兼容兜底。
- 前端只使用本次 SSE 运行携带的快照，不把一个消息的配置泄漏到另一条消息。
- 该改动不改变 AgentScope 内部单次工具调用的版本级超时优先级；本次统一的是子代理整体委派和前端挂起提示所使用的全局配置。
- 不新增数据库字段、不新增迁移、不启动服务、不改变已有取消接口。

## 验证计划

后端：

- 验证子代理超时解析改为调用 `load_agent_max_toolcall_timeout`。
- 验证子代理请求和 `wait_for` 使用配置值。
- 验证超时仍关闭 async generator。
- 验证流式聊天下发 `run_config` 事件。

前端：

- 验证 `run_config` 能写入当前消息。
- 验证看门狗使用消息配置值，而不是固定 180 秒。
- 验证缺少或非法快照时使用 180 秒兼容兜底。
- 运行前端契约测试和 `vue-tsc --noEmit`。
