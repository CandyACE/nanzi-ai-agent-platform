# Bash 环境探测与输入框风险横幅 —— 设计文档

日期：2026-08-21
分支：`dev-agentscope`

## 1. 背景与目标

平台里 ai 通过 Bash（别名 `exec_command` / `bash` / `Bash`）执行命令时，实际走的是平台自己的
`CancellableLocalBackend` → `asyncio.create_subprocess_exec`，跑在**后端进程所在的环境**里，
并没有每次 bash 单独起一个 Docker 沙箱。

因此在**开发机**上，"bash 跑在哪" == "后端跑在哪" == **宿主机**（有真实命令风险）；
在**生产容器**里则跑在 Docker 的 `/app` 内（相对安全）。

用户诉求：当 bash 被执行时，在**聊天输入框上方的横向横幅条**里提示当前 bash 运行在哪个环境；
若在宿主机则给出风险提示，建议 Docker 部署或改用 sandbox。

### 成功标准
- 用户一句"让 ai 执行个命令"，聊天输入框上方出现横幅，明示 bash 运行环境。
- 宿主机环境：琥珀黄风险文案；容器环境：绿色安全文案。
- 横幅会随对话推进自动消失、可手动关闭，同一轮多次 bash 只提示一次。

## 2. 设计决策（已与用户确认）

| 项 | 决策 |
| --- | --- |
| 触发时机 | 一轮对话内**首个** Bash 工具调用触发 |
| 重复策略 | 同一轮后续 bash 调用**不再重复**触发（不闪烁） |
| 关闭时机 | 该轮 ai 完整回复结束（流结束）自动关闭；用户可手动 × 关闭当前条 |
| 宿主机颜色 | 琥珀黄（温和但醒目，dev 场景不过冲） |
| 容器颜色 | 绿色（"Bash 运行在容器沙箱，环境安全"） |
| 数据获取 | 后端进程启动时探测一次并缓存；通过 SSE 事件内嵌下发（零额外请求） |

## 3. 架构与数据流

```
后端进程启动
   └→ 探测一次环境 bash_runtime_env ∈ {host, docker}（模块级缓存，进程生命周期内恒定）
                │
                │  本轮第 1 次 Bash：Bash 工具被调用
                ▼
event_stream (map_standard_agentscope_event) 在 TOOL_CALL_START(Bash) 且本轮首条时
   追加一帧 SSE 事件  {type:"bash_env", env:"host"|"docker"}
                │
                ▼
前端 dispatchAgentscopeStreamEvent 新增 case "bash_env"
   把 env 写入当前消息/会话的横幅状态 → ChatInput banner slot 展示横幅
                │
                ▼
该轮流结束（done 帧）→ 前端清空本轮横幅展开状态 → 横幅自动关闭
```

### 为什么"在哪跑"= "后端进程环境"
bash 由后端进程内的 `CancellableLocalBackend` 以 `asyncio.create_subprocess_exec` 直接派生，
未做每调用一次容器沙箱化。故探测对象即**后端进程所处环境**，且为进程级恒定属性，探测一次足够。

## 4. 后端改动

### 4.1 环境探测工具（新增，进程级一次性）
新增一个纯函数（放工具命名空间，如 `app/utils/env.py` 或并入 `app/core/config.py` 附近），按优先级判定：

1. 存在 `/.dockerenv` → `docker`
2. 读 `/proc/self/cgroup`，含 `docker` 或 `kubepods` → `docker`（注意仅识别容器，不打标签）
3. 存在 `/app`（平台容器内挂载/工作目录标志）→ `docker`
4. 否则 → `host`

结果以模块级常量缓存，进程生命周期内不重复探测。

> 说明：`kubepods` 表示在 k8s Pod 内运行，本质仍是容器，纳入 `docker` 分类即可，避免误标。

### 4.2 SSE 事件发射
在 `app/services/ai/runtime/agentscope/event_stream.py` 的 `map_standard_agentscope_event`
`TOOL_CALL_START` 分支中：当本次工具名为 `Bash` 且**当前这一轮尚未发过** `bash_env` 时，
在既有 `{"type":"log","title":"调用工具: Bash"...}` 帧之后额外 `yield` 一帧：

```python
yield {"type": "bash_env", "env": "host" | "docker"}
```

"本轮是否已发"需要一个随 `state` 走的状态标记（如 `state.setdefault("bash_env_emitted", False)`），
`new_native_stream_state` 增加该字段，state 随会话流转自然覆盖"整轮结束"语义。

### 4.3 不改动项
- 不新建后端 HTTP 端点（方案 A 决策，走 SSE 内嵌）。
- 不改工具注册表 / 权限预检。
- 不触碰 system.py 等 admin 标题接口。

## 5. 前端改动

### 5.1 SSE 分发
`frontend/src/utils/agentscopeSseHandlers.ts` 的 `dispatchAgentscopeStreamEvent` 增加：

```ts
case "bash_env":
  // 置位当前消息/会话的横幅状态： env + 已在本轮置位，避免重复弹
  return true;
```

横幅状态建议挂在会话级 store（供 `ChatInput` banner slot 读取），字段：
```ts
bashEnv: "host" | "docker" | null;   // null = 不显示
```

### 5.2 横幅
- **ChatInput banner slot（已授权占用）**：新增横幅渲染，读会话 store 的 `bashEnv`。
- 样式：
  - `docker` → 绿色浅底 + `🟢 Bash 运行在容器沙箱（/app），环境安全`
  - `host` → 琥珀黄浅底 + `⚠️ Bash 正在宿主机上执行，存在命令风险，建议 Docker 部署或改用 sandbox`
  - 右侧 × 按钮 → 手动关闭（置 `bashEnv = null`）
- **流结束（done 帧）自动清除**：连接 SSE 关闭/消息终态时，将会话 `bashEnv` 复位为 `null`，
  使下一轮有 bash 时重新经 `case "bash_env"` 触发。
- 横幅只做定位与提示，无持久按钮交互（YAGNI）。

> 注意：`ChatInput.vue` 中的 LTM 遗留死代码/未用 props 不在本次改动范围，仅占用 banner slot。

## 6. 错误处理与边界
- 探测读取 `/proc/self/cgroup`、`/.dockerenv` 失败（平台环境扰动）时**静默降级为 host**，
  并记录一条 debug 日志；不影响主流程。
- 横幅状态为 `null` 时不渲染任何 DOM，不影响现有布局。
- 同一轮"流结束自动关闭"以 SSE 连接终态/消息 done 为准，避免中途异常导致横幅残留。

## 7. 测试
- 后端：对探测函数做单测（mock `/.dockerenv`/cgroup 内容/目录存在性 → 断言分类）。
- 前端：纯契约测试覆盖 `dispatchAgentscopeStreamEvent` 收到 `bash_env` 时置位、重复 `bash_env`
  不重复触发、done 后复位。
- 类型检查：`vue-tsc --noEmit`。

## 8. 交付范围
- 后端探测工具 + SSE `bash_env` 发射（含 state 去重）。
- 前端 SSE handler `case "bash_env"` + 会话 store 字段 + ChatInput banner slot 横幅 + 手动关闭/流结束复位。
- 单测与类型检查。
- 由用户在控制台执行 `./dev.sh` 联调（Agent 不代跑）。

## 9. 备选方案（已评估未采用）
- **B：专门 /api 端点**：进入聊天页先拉一次。缺点多一次请求、各页需自行接入、时机不如 SSE 精准。
- **C：A+B 结合**：功能最全但工作量与维护面更大，超出"输入框横幅"这一需求。
- **每次调用都弹**：造成同一轮多次闪烁，已否决。