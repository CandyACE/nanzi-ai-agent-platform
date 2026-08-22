# Docker 沙箱执行隔离与用户容器启动 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Docker 策略下的 Bash 在用户 Docker 工作区初始化失败时安全终止，并提供仅在 Docker 生效策略下可见的用户容器手动启动入口。

**Architecture:** 在工作区层定义稳定的 Docker 沙箱异常、有限初始化重试和实际执行后端元数据；Agent 构建阶段遇到 Docker 初始化失败时 fail-closed，禁止原始本地 Bash 继续执行。新增当前用户的 workspace ensure API，前端在现有 `ChatInput` 的 banner 插槽内显示启动、运行、失败和重试状态，状态只使用后端 effective policy/runtime 信息。

**Tech Stack:** Python 3.11、FastAPI、pytest、Vue 3、TypeScript、Vite、现有 SSE 事件和 Axios API 封装。

---

### Task 1: 定义工作区错误、实际后端元数据和初始化重试边界

**Files:**
- Modify: `app/services/ai/runtime/agentscope/workspace.py:20-45, 600-715, 1062-1191`
- Test: `tests/ai/runtime/test_agentscope_workspace.py`

- [ ] **Step 1: 写失败测试，验证 Docker 初始化只允许一次可恢复重试**

在 `tests/ai/runtime/test_agentscope_workspace.py` 增加一个 fake Docker workspace：第一次 `initialize()` 抛出瞬态异常，第二次成功；断言初始化次数为 2，最终返回 Docker workspace。再增加不可恢复权限错误只调用一次的测试。

```python
async def test_docker_workspace_retries_transient_initialize_once(monkeypatch, tmp_path):
    attempts = 0

    class FakeDockerWorkspace:
        instances = []

        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.is_alive = False
            self._container = type("Container", (), {"id": "container-1"})()
            FakeDockerWorkspace.instances.append(self)

        async def initialize(self):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise ConnectionError("temporary daemon connection reset")
            self.is_alive = True

        async def close(self):
            self.is_alive = False

    monkeypatch.setattr("agentscope.workspace.DockerWorkspace", FakeDockerWorkspace)
    monkeypatch.setattr(workspace_module.asyncio, "sleep", AsyncMock())

    result = await workspace_module._policy_docker_workspace(
        [], workspace_id="alice__1", sandbox_user_key="alice__1", workspace_root=str(tmp_path)
    )

    assert result._platform_sandbox_policy == "docker"
    assert attempts == 2


async def test_docker_workspace_does_not_retry_permission_failure(monkeypatch, tmp_path):
    attempts = 0

    class FakeDockerWorkspace:
        def __init__(self, **kwargs):
            self.is_alive = False

        async def initialize(self):
            nonlocal attempts
            attempts += 1
            raise PermissionError("docker socket denied")

        async def close(self):
            pass

    monkeypatch.setattr("agentscope.workspace.DockerWorkspace", FakeDockerWorkspace)

    with pytest.raises(workspace_module.DockerSandboxUnavailableError) as exc_info:
        await workspace_module._policy_docker_workspace(
            [], workspace_id="alice__1", sandbox_user_key="alice__1", workspace_root=str(tmp_path)
        )

    assert attempts == 1
    assert exc_info.value.reason_code == "docker_daemon_unavailable"
```

The test patches `workspace_module.asyncio.sleep` with an `AsyncMock` so it never waits; the production API must remain a single retry with a 500ms delay.

- [ ] **Step 2: 运行失败测试，确认当前实现没有重试和稳定异常**

Run:

```bash
venv/bin/python -m pytest tests/ai/runtime/test_agentscope_workspace.py -k 'retries_transient_initialize_once or does_not_retry_permission_failure' -q
```

Expected: FAIL because the current implementation performs one initialization attempt and propagates the raw exception.

- [ ] **Step 3: 实现稳定异常和最小重试逻辑**

在 `workspace.py` 定义 `DockerSandboxUnavailableError(RuntimeError)`，包含 `reason_code`、`user_message` 和可选原始异常信息；增加错误分类函数，只把连接瞬态错误和容器启动瞬态错误标记为可重试。`_policy_docker_workspace()` 对可重试错误最多等待 500ms 后再初始化一次；每次失败都关闭已创建的 workspace。权限、镜像、挂载和端口错误直接转换为稳定错误码。

保留原有 workspace label、用户目录挂载到容器 `/workspace` 的逻辑路径契约和 `as_ws_<workspace_id>` 命名。为成功 workspace 增加只读元数据属性，例如 `_platform_execution_backend = "docker"`、`_platform_workspace_id` 和从容器对象读取的 `_platform_container_id`，供 API 和 SSE 使用。

- [ ] **Step 4: 运行测试确认重试和异常分类通过**

Run:

```bash
venv/bin/python -m pytest tests/ai/runtime/test_agentscope_workspace.py -k 'retries_transient_initialize_once or does_not_retry_permission_failure' -q
```

Expected: PASS.

### Task 2: Docker 策略 fail-closed，禁止原始 Bash 回退宿主

**Files:**
- Modify: `app/services/ai/runtime/agentscope/workspace.py:1062-1191, 1581-1600`
- Modify: `app/services/ai/runners/assistant_agent_runner.py:1397-1407`
- Test: `tests/ai/runtime/test_agentscope_workspace.py`
- Test: `tests/ai/runtime/test_agentscope_workspace_toolkit.py`

- [ ] **Step 1: 写失败测试，验证 Docker 工作区失败不会返回可执行的原始工具**

新增测试：mock effective policy 为 Docker、mock `get_local_workspace()` 抛出 `DockerSandboxUnavailableError`，调用 agent 构建路径时断言异常携带稳定错误码；另外直接测试 `bind_configured_tools_to_workspace(None, [bash_spec])` 在 Docker fail-closed 参数/上下文下不再返回原始 Bash。

```python
async def test_docker_workspace_failure_is_not_silently_bound_to_local_bash(monkeypatch):
    async def fail_workspace(**kwargs):
        raise workspace_module.DockerSandboxUnavailableError(
            "docker daemon unavailable",
            reason_code="docker_daemon_unavailable",
            user_message="Docker 沙箱不可用，Bash 未执行。",
        )

    monkeypatch.setattr(runner_module, "get_local_workspace", fail_workspace)

    with pytest.raises(workspace_module.DockerSandboxUnavailableError) as exc_info:
        await runner._build_native_agent(
            native_model=fake_model,
            tools=[bash_spec],
            system_content="system",
            max_steps=1,
            primary_model_name="test-model",
        )

    assert exc_info.value.reason_code == "docker_daemon_unavailable"
```

Construct the runner with the existing test factory in `tests/ai/runtime/test_agentscope_workspace.py`, then patch only its imported `get_local_workspace`; do not invoke a real model or Docker daemon.

- [ ] **Step 2: 运行失败测试，确认当前 fail-open 行为被捕获**

Run:

```bash
venv/bin/python -m pytest tests/ai/runtime/test_agentscope_workspace.py tests/ai/runtime/test_agentscope_workspace_toolkit.py -k 'not_sandbox or docker_workspace_failure' -q
```

Expected: the new failure test fails because the current workspace path returns `None` and the toolkit binder leaves the local Bash spec unchanged.

- [ ] **Step 3: 实现 fail-closed 工具绑定和运行时错误传播**

让 `get_local_workspace()` 在 Docker 策略下保留并传播 `DockerSandboxUnavailableError`，同时继续把 local/e2b/ssh 的既有错误语义限制在各自策略内。`bind_configured_tools_to_workspace()` 不能把 Docker 初始化失败转换成原始本地工具；在 runner 中让异常在 Agent 初始化前传播到现有聊天错误流，确保模型没有机会调用 Bash。

错误消息统一为用户可读中文，例如：`Docker 沙箱不可用，Bash 未执行：请检查 Docker daemon、镜像和权限。`；完整异常只写服务端日志。

- [ ] **Step 4: 运行后端聚焦测试**

Run:

```bash
venv/bin/python -m pytest tests/ai/runtime/test_agentscope_workspace.py tests/ai/runtime/test_agentscope_workspace_toolkit.py -q
```

Expected: PASS，且原有 local、Docker 成功绑定、文件工具宿主映射测试不回归。

### Task 3: 增加当前用户 Docker 工作区 ensure API

**Files:**
- Modify: `app/api/v1/endpoints/sandbox.py:1-92`
- No change: `app/api/v1/api.py:17` already mounts `sandbox.router` under the secured v1 router; the new endpoint remains API-key protected and is not admin-only.
- Modify: `app/services/ai/runtime/agentscope/workspace.py` to expose a small metadata/ensure helper
- Test: `tests/api/v1/test_sandbox_connection.py`

- [ ] **Step 1: 写失败测试，覆盖 effective policy、当前用户隔离和容器状态返回**

新增一个受 API key 保护的 `POST /sandbox/docker/workspace/ensure` 测试，传入 `conversation_id`，mock 当前用户身份和 Docker workspace，断言返回 `status=running`、`execution_backend=docker`、`workspace_id` 和 `container_id`。再覆盖：当前策略为 local 时返回 `docker_policy_not_effective`；缺少 `conversation_id` 或用户身份时返回 400/稳定错误码；普通用户只能确保自己的 workspace。

```python
async def test_ensure_docker_workspace_returns_running_metadata(monkeypatch):
    fake_workspace = type(
        "FakeWorkspace",
        (),
        {
            "_platform_sandbox_policy": "docker",
            "_platform_execution_backend": "docker",
            "_platform_workspace_id": "alice__1",
            "_platform_container_id": "container-1",
        },
    )()

    async def ensure(**kwargs):
        return fake_workspace

    monkeypatch.setattr(sandbox_endpoint_module, "ensure_docker_workspace", ensure)

    result = await sandbox_endpoint_module.ensure_docker_workspace_endpoint(
        request=sandbox_endpoint_module.DockerWorkspaceEnsureRequest(conversation_id="c1"),
        user_info={"user_id": 1, "user_name": "alice", "role": "user"},
    )

    assert result.data["status"] == "running"
    assert result.data["execution_backend"] == "docker"
    assert result.data["container_id"] == "container-1"
```

Call the endpoint function directly with its Pydantic request model and `user_info` dictionary, then inspect the returned `StandardResponse.data` mapping; this keeps the test independent of HTTP middleware while covering the endpoint contract.

- [ ] **Step 2: 运行失败测试，确认接口尚不存在**

Run:

```bash
venv/bin/python -m pytest tests/api/v1/test_sandbox_connection.py -k 'ensure_docker_workspace' -q
```

Expected: FAIL because no user workspace ensure endpoint/helper exists.

- [ ] **Step 3: 实现 workspace ensure helper 和 API**

在 workspace 模块增加 `ensure_docker_workspace(...)`：

- 解析 effective policy，非 Docker 立即抛出 `docker_policy_not_effective`；
- 解析当前用户身份，缺失时抛出 `docker_workspace_identity_required`；
- 调用现有 `get_local_workspace()`，复用同一用户 workspace cache 和一次初始化重试；
- 从 `sandbox_ws` 读取 workspace/container 元数据；
- 不在容器中执行 Bash、hostname 或额外健康命令。

在 `sandbox.py` 增加当前登录用户可调用的非管理员接口。接口使用 `require_api_key`，只接受当前用户的 `conversation_id`，将稳定异常转换为安全的 HTTP 错误响应，不返回 socket、宿主路径或认证信息。保留已有 admin-only 镜像预构建接口不变。

- [ ] **Step 4: 运行 API 测试**

Run:

```bash
venv/bin/python -m pytest tests/api/v1/test_sandbox_connection.py -q
```

Expected: PASS.

### Task 4: 上报实际 Bash 执行后端

**Files:**
- Modify: `app/services/ai/runtime/agentscope/event_stream.py:21-41, 480-487`
- Modify: `app/services/ai/runners/assistant_agent_runner.py` to seed runtime execution metadata into the stream state
- Modify: `tests/ai/runtime/test_event_stream_observability.py`

- [ ] **Step 1: 写失败测试，验证 SSE 不再只读取配置策略**

新增测试：当运行时 state 标记 `execution_backend=host` 时，即使配置 `sandbox_policy=docker`，Bash 环境事件也不能发送 `docker`；当 workspace 实际标记 Docker 时才发送 `docker`。Docker 初始化异常不发送成功的 `bash_env`。

```python
async def test_bash_env_uses_bound_execution_backend(monkeypatch):
    from unittest.mock import AsyncMock

    monkeypatch.setattr(
        config_module.ConfigService,
        "get",
        AsyncMock(return_value="docker"),
    )
    state = new_native_stream_state()
    state["execution_backend"] = "host"
    event = SimpleNamespace(
        type="TOOL_CALL_START",
        tool_call_id="t1",
        tool_call_name="Bash",
    )
    chunks = [
        chunk
        async for chunk in event_stream_module.map_standard_agentscope_event(
            event,
            state=state,
        )
    ]
    assert [chunk["env"] for chunk in chunks if chunk.get("type") == "bash_env"] == ["host"]
```

The production change passes `state` into the environment resolver; the test uses `map_standard_agentscope_event`, which is the actual Bash `TOOL_CALL_START` path.

- [ ] **Step 2: 运行失败测试**

Run:

```bash
venv/bin/python -m pytest tests/ai/runtime/test_event_stream_observability.py -k 'bound_execution_backend' -q
```

Expected: FAIL because `_sandbox_bash_env()` currently derives the value only from `sandbox_policy`.

- [ ] **Step 3: 实现实际后端状态传播**

在 Agent runner 完成 workspace/tool binding 后，将 `execution_backend` 写入已有 stream state；event stream 只读取这个绑定结果。保留 local/e2b/ssh 的现有类型。对于 Docker，只有 `sandbox_ws` 成功绑定后才产生 `docker` 事件。

- [ ] **Step 4: 运行事件观测测试**

Run:

```bash
venv/bin/python -m pytest tests/ai/runtime/test_event_stream_observability.py -q
```

Expected: PASS.

### Task 5: 在输入框上方增加 Docker 用户容器启动入口

**Files:**
- Modify: `frontend/src/components/chat/BashEnvBanner.vue`
- Modify: `frontend/src/views/EmbedChat.vue:1184-1253`
- No change: `ContextUsage.sandbox_policy` is already populated with the effective policy by the existing context-usage endpoint.
- Test: `tests/frontend/test_bash_env_banner_contract.py`
- Create: `tests/frontend/test_chat_sandbox_workspace_contract.py`

- [ ] **Step 1: 写失败契约测试，验证入口位置和显示条件**

新增源代码契约测试，要求：

- `BashEnvBanner` 支持 Docker workspace status/start/retry props/events；
- `EmbedChat.vue` 在现有 `ChatInput` `#banner` 插槽内接入启动动作；
- 有明确的 `effectivePolicy === "docker"` 或等价后端状态判断；
- local、e2b、ssh 和 runtime-downgraded local 不渲染启动入口；
- 启动文案包含 `启动我的 Docker 沙箱` 和 `重试启动`；
- 请求使用当前 `conversationId` 调用 ensure endpoint。

```python
def test_docker_workspace_action_is_rendered_only_for_effective_docker_policy():
    source = (ROOT / "frontend/src/views/EmbedChat.vue").read_text()
    banner = (ROOT / "frontend/src/components/chat/BashEnvBanner.vue").read_text()
    assert "/api/v1/sandbox/docker/workspace/ensure" in source
    assert "启动我的 Docker 沙箱" in banner
    assert "重试启动" in banner
    assert "docker" in source
```

- [ ] **Step 2: 运行失败契约测试**

Run:

```bash
venv/bin/python -m pytest tests/frontend/test_chat_sandbox_workspace_contract.py -q
```

Expected: FAIL because the new action and API call do not yet exist.

- [ ] **Step 3: 实现 banner 状态和 EmbedChat 请求**

扩展 `BashEnvBanner.vue`：

- Docker banner 接收 `workspaceStatus: idle | starting | running | error`；
- 接收 `workspaceError`；
- 仅 Docker 分支显示启动、刷新或重试按钮；
- 启动中禁用按钮；
- 保留现有忽略/关闭提示行为；
- 不在非 Docker分支产生用户容器入口。

在 `EmbedChat.vue`：

- 以 context usage 的 effective policy/runtime state 作为显示条件；
- 在 `#banner` 内维护当前用户工作区状态；
- 点击启动/重试时以当前 `conversationId` 调用 ensure endpoint；
- 成功显示 running/container 状态并保留现有 BashEnvBanner；
- 失败显示后端安全提示；
- 切换会话或策略后清理旧状态，避免把一个会话的容器状态显示到另一个会话。

- [ ] **Step 4: 运行前端契约和类型检查**

Run:

```bash
venv/bin/python -m pytest tests/frontend/test_bash_env_banner_contract.py tests/frontend/test_chat_sandbox_workspace_contract.py -q
cd frontend && npx vue-tsc --noEmit
```

Expected: PASS.

### Task 6: 全量聚焦回归和差异检查

**Files:**
- Test only: existing backend/frontend test files from Tasks 1-5

- [ ] **Step 1: 运行后端回归**

Run:

```bash
venv/bin/python -m pytest tests/ai/runtime/test_agentscope_workspace.py tests/ai/runtime/test_agentscope_workspace_toolkit.py tests/ai/runtime/test_event_stream_observability.py tests/api/v1/test_sandbox_connection.py -q
```

Expected: PASS.

- [ ] **Step 2: 运行前端回归**

Run:

```bash
venv/bin/python -m pytest tests/frontend/test_bash_env_banner_contract.py tests/frontend/test_chat_sandbox_workspace_contract.py tests/frontend/test_chat_context_usage_contract.py -q
cd frontend && npx vue-tsc --noEmit
```

Expected: PASS.

- [ ] **Step 3: 运行 Python 编译和差异检查**

Run:

```bash
venv/bin/python -m compileall -q app tests/ai/runtime tests/api/v1
git diff --check -- app/services/ai/runtime/agentscope/workspace.py app/services/ai/runtime/agentscope/event_stream.py app/services/ai/runners/assistant_agent_runner.py app/api/v1/endpoints/sandbox.py frontend/src/components/chat/BashEnvBanner.vue frontend/src/views/EmbedChat.vue tests
```

Expected: no output and exit code 0. Do not stage or commit unrelated existing worktree changes.
