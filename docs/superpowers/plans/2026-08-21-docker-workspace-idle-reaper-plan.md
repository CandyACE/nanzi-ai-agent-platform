# Docker 用户沙箱空闲回收 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 固定将每个用户的 Docker 沙箱挂载到 `agentscope_workspace_root/user_key`，并在用户沙箱空闲 30 分钟后自动关闭回收，同时移除宿主机挂载目录配置入口。

**Architecture:** `workspace.py` 维护用户级 Docker workspace 的最近使用时间与回收任务；回收任务在应用 lifespan 启动/关闭，默认每 60 秒扫描，回收时清理会话 workspace 缓存并关闭 Docker/MCP 资源。Docker host workdir 不再读取配置，而由已解析的 workspace root 与用户 key 拼接生成。前端仅保留 Docker 基础镜像配置。

**Tech Stack:** Python 3.11、FastAPI lifespan、asyncio、AgentScope DockerWorkspace、pytest、Vue 3/TypeScript。

---

### Task 1: 添加失败测试

**Files:**
- Modify: `tests/ai/runtime/test_agentscope_workspace.py`
- Create: `tests/frontend/test_sandbox_docker_host_workdir_contract.py`

- [ ] 测试 Docker host workdir 必须等于 `<workspace_root>/<user_key>`，且不读取旧配置。
- [ ] 测试空闲 Docker workspace 会被回收，未超时 workspace 保持存活。
- [ ] 测试回收会清理 Docker 引用与会话缓存，下一次请求可重新创建。
- [ ] 测试前端不再展示 `sandbox_docker_host_workdir`。

### Task 2: 实现 Docker 生命周期回收

**Files:**
- Modify: `app/services/ai/runtime/agentscope/workspace.py`
- Modify: `app/main.py`

- [ ] 记录用户 Docker workspace 的 `last_used_at`，复用时刷新。
- [ ] 添加默认 1800 秒空闲阈值、60 秒扫描间隔，以及可测试的扫描/启停函数。
- [ ] 回收时安全关闭 Docker workspace 和关联本地 workspace，清理缓存引用。
- [ ] 在 FastAPI lifespan 启动回收任务，关闭时取消任务并释放剩余 workspace。

### Task 3: 固定用户目录并移除配置入口

**Files:**
- Modify: `app/services/ai/runtime/agentscope/workspace.py`
- Modify: `frontend/src/views/SystemConfig.vue`
- Test: `tests/frontend/test_sandbox_docker_host_workdir_contract.py`

- [ ] Docker 创建参数使用 `os.path.join(root, user_key)` 作为 host workdir。
- [ ] 删除前端 Docker 策略字段、文案和动态显示列表中的 `sandbox_docker_host_workdir`。
- [ ] 保留旧数据库字段但运行时忽略，避免历史配置继续控制挂载路径。

### Task 4: 验证

- [ ] 运行 Docker workspace focused pytest。
- [ ] 运行前端契约测试与 TypeScript 检查（如环境依赖可用）。
- [ ] 运行 `ruff`、`py_compile`、`git diff --check`。

