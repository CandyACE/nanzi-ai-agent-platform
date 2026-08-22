# Docker 沙箱用户容器启动与执行隔离设计

## 背景

当前 Docker 沙箱支持预构建镜像，但用户级 Docker 工作区容器仍由会话首次初始化时懒启动。Docker 工作区初始化失败后，现有工具绑定逻辑可能把原始 Bash 工具放行，导致命令回退到平台进程所在环境执行；同时前端 Bash 环境横幅按策略配置显示，不能证明本次 Bash 已绑定到 Docker 容器。

本次变更只处理用户级运行容器，不重复实现镜像预构建。预构建镜像只负责提供运行时可复用的镜像缓存；用户容器由工作区管理器创建、缓存和回收。

## 目标

1. Docker 工作区初始化失败时明确提示用户，本次 Bash 不执行，禁止静默回退宿主。
2. 对 Docker 工作区初始化增加一次有限重试，但不自动重试或重复执行用户 Bash 命令。
3. 提供当前用户手动启动/检查 Docker 工作区容器的接口和聊天入口。
4. 手动启动只创建或复用用户容器，不执行任何命令。
5. Bash 环境提示基于实际绑定结果，不再只依据配置策略。
6. 只有实际生效策略为 Docker 时，才显示启动入口和 Docker 容器状态；local、e2b、ssh 或 Docker 策略被运行时守卫降级为 local 时均不显示。

## 非目标

- 不修改 Docker 镜像预构建、手动导入或基础镜像配置流程。
- 不允许 Docker 不可用时自动切换到宿主 Bash。
- 不增加自动 pull 镜像或自动执行用户命令的逻辑。
- 不改变 E2B、SSH 和 local 策略的既有执行语义。

## 方案

### 1. 工作区初始化与失败边界

保留现有按用户维度缓存 Docker 工作区的机制：缓存键使用工作区根目录、用户身份和 Docker 策略，容器继续使用 `as_ws_<workspace_id>` 命名，并由空闲回收器清理。

`get_local_workspace()` 在 Docker 策略下负责获得 `(sandbox_ws, local_ws)`。初始化失败时抛出带有稳定错误码的沙箱不可用异常，调用方在进入 Agent 工具循环前终止本次运行。异常中包含阶段信息，例如 Docker daemon 连接、镜像检查、容器创建/启动、网关端口绑定或宿主工作区初始化。

只有明确配置为 local 且实际生效策略为 local 时，才允许使用宿主 Bash。Docker 策略下不再把 `workspace=None` 当成正常的工具绑定结果。

### 2. 重试策略

重试只包裹 Docker 工作区的创建/启动阶段：

- 最多一次重试，间隔约 500ms；
- 连接瞬断、容器创建竞争或启动瞬态错误允许重试；
- socket 权限不足、Docker daemon 持续不可达、镜像不存在、挂载路径错误和端口配置错误不重复重试；
- 不重试 AgentScope 的 Bash 调用，不重复执行任何用户 Bash 命令；
- 两次初始化均失败时返回稳定错误码和可操作提示。

### 3. 手动启动接口

新增面向当前登录用户的工作区确保接口，使用当前用户身份和当前会话 ID：

```http
POST /api/v1/sandbox/docker/workspace/ensure
```

请求体至少包含 `conversation_id`。接口复用同一套有效策略解析、用户身份解析、镜像检查、Docker 工作区初始化和一次重试逻辑，返回：

- `execution_backend: "docker"`；
- `workspace_id`；
- `container_id`（可用于诊断，不暴露宿主敏感路径）；
- `status: "running"` 或稳定失败状态；
- 必要时返回 `reason_code`、用户提示和下一步建议。

接口只确保容器存在并运行，不在容器内执行 Bash、hostname 或健康检查命令。用户容器继续由现有 idle reaper 在空闲超时后回收。

### 4. 实际执行后端与前端入口

运行时在工作区绑定成功后记录实际执行后端。Bash 环境 SSE 事件使用这个运行时结果：

- Docker 工作区成功绑定：`docker`；
- local 策略：`host` 或当前平台进程环境；
- 初始化失败：不发送成功的 Docker 环境事件，改为发送沙箱不可用错误。

聊天输入区的 Docker 工作区入口只在实际生效策略为 Docker 时渲染。入口包括：

- 未启动或状态未知：`启动我的 Docker 沙箱`；
- 初始化中：`Docker 沙箱启动中...`，按钮禁用；
- 已运行：显示 Docker 沙箱已运行，可提供刷新状态动作；
- 初始化失败：显示错误原因和 `重试启动`；
- 非 Docker 生效策略：整个入口不渲染。

前端不能仅用原始 `sandbox_policy` 判断显示条件；应使用后端下发的 effective policy/runtime state，避免平台运行在 Docker 时把被降级的 Docker 策略误显示成可启动。

## 数据流

```text
用户点击启动
  -> 前端检查 effective policy == docker
  -> POST /api/v1/sandbox/docker/workspace/ensure
  -> 当前用户身份 + conversation_id
  -> get_local_workspace / Docker workspace cache
  -> inspect 已预构建镜像
  -> create_or_replace + start as_ws_<workspace_id>
  -> 返回 execution_backend/container_id/status
  -> 前端显示已运行

首次 Bash
  -> 复用同一用户 Docker workspace
  -> 绑定 sandbox Bash
  -> 使用实际 backend 上报 bash_env
  -> Docker 初始化失败则终止，不执行宿主 Bash
```

## 错误处理

统一使用可测试的错误码，至少覆盖：

- `docker_policy_not_effective`：当前实际策略不是 Docker；
- `docker_daemon_unavailable`：无法连接 Docker daemon；
- `docker_image_unavailable`：运行时镜像不存在或不可 inspect；
- `docker_workspace_start_failed`：容器创建、启动、网关或挂载失败；
- `docker_workspace_identity_required`：缺少当前用户身份。

API 错误不得泄露 Docker socket、宿主绝对路径或认证信息；服务端日志保留完整异常用于诊断。

## 测试设计

### 后端

- Docker 工作区初始化成功时返回 Docker workspace，并绑定 Bash 到 sandbox workspace；
- Docker 初始化失败时经过一次允许的重试后仍失败，抛出稳定异常；
- Docker 初始化失败时原始 Bash 不会被放行到本地 backend；
- 权限错误、镜像缺失等不可恢复错误不重复重试；
- 手动 ensure 接口只使用当前用户身份，成功返回 running 和实际容器标识；
- local/e2b/ssh 或 Docker 被运行时守卫降级为 local 时拒绝 Docker ensure；
- Bash 环境事件来自实际绑定结果。

### 前端

- effective policy 为 Docker 时渲染启动入口；
- effective policy 为 local、e2b、ssh 或未就绪时不渲染入口；
- 启动中、成功、失败和重试状态文案正确；
- Docker 初始化错误不会显示为成功的 Docker Bash 环境。

### 验证命令

```bash
venv/bin/python -m pytest tests/ai/runtime/test_agentscope_workspace.py tests/ai/runtime/test_agentscope_workspace_toolkit.py tests/api/v1/test_sandbox_connection.py -q
venv/bin/python -m pytest tests/frontend/test_bash_env_banner_contract.py tests/frontend/test_sandbox_docker_prebuild_placement_contract.py -q
cd frontend && npx vue-tsc --noEmit
```

