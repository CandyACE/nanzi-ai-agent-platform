# Docker 预构建实时日志 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让管理员页面点击“预构建镜像”后实时看到 Docker 构建阶段、原始日志和完整失败原因。

**Architecture:** 保留现有同步预构建接口作为兼容入口；为管理员页面增加专用 SSE 接口。预构建服务通过可选异步回调转发阶段和 Docker build stream，SSE 端点用任务队列把事件推送给前端。前端用 `fetch().getReader()` 消费 SSE，在配置卡片中保留可复制的日志和最终错误。

**Tech Stack:** FastAPI `StreamingResponse`、Python `asyncio.Queue`、aiodocker build stream、Vue 3 Composition API、TypeScript。

---

### Task 1: 后端预构建服务暴露构建事件

**Files:**
- Modify: `app/services/ai/runtime/agentscope/docker_prebuild.py`
- Test: `tests/ai/runtime/test_docker_prebuild.py`

- [ ] **Step 1: Write the failing test**

为 `prebuild_docker_workspace_image` 传入异步事件回调，断言 Docker build stream 的日志被逐条转发，且不改变最终成功结果。

- [ ] **Step 2: Run the test to verify it fails**

Run: `venv/bin/python -m pytest --confcutdir=tests/ai/runtime tests/ai/runtime/test_docker_prebuild.py -k event -q`

Expected: FAIL，因为当前函数不接受事件回调，也不会转发 build stream。

- [ ] **Step 3: Write minimal implementation**

给预构建函数增加可选异步回调；在准备上下文、检查缓存、开始构建、收到 Docker stream、构建完成或异常时发送结构化事件。无回调时保持现有同步接口行为。

- [ ] **Step 4: Run the test to verify it passes**

Run: `venv/bin/python -m pytest --confcutdir=tests/ai/runtime tests/ai/runtime/test_docker_prebuild.py -k event -q`

Expected: PASS。

### Task 2: 增加管理员专用 SSE 预构建接口

**Files:**
- Modify: `app/api/v1/endpoints/sandbox.py`
- Test: `tests/api/v1/test_sandbox_connection.py`

- [ ] **Step 1: Write the failing test**

调用 SSE 端点并替换预构建服务为带事件回调的假实现，断言响应使用 `text/event-stream`，包含阶段、日志、完成或错误事件，并继续执行管理员校验。

- [ ] **Step 2: Run the test to verify it fails**

Run: `venv/bin/python -m pytest --confcutdir=tests/api/v1 tests/api/v1/test_sandbox_connection.py -k prebuild_stream -q`

Expected: FAIL，因为当前没有管理员预构建 SSE 路由。

- [ ] **Step 3: Write minimal implementation**

新增 `POST /api/v1/admin/sandbox/docker/prebuild/stream`。端点创建 `asyncio.Queue` 和后台预构建任务，以 SSE `event` + JSON `data` 推送阶段、日志、最终结果和错误；客户端断开时取消任务并释放资源。

- [ ] **Step 4: Run the test to verify it passes**

Run: `venv/bin/python -m pytest --confcutdir=tests/api/v1 tests/api/v1/test_sandbox_connection.py -k prebuild_stream -q`

Expected: PASS。

### Task 3: 管理员页面实时消费和展示日志

**Files:**
- Modify: `frontend/src/views/SystemConfig.vue`
- Test: `tests/frontend/test_sandbox_docker_prebuild_placement_contract.py`

- [ ] **Step 1: Write the failing test**

断言页面调用预构建 SSE 路径、使用 `response.body.getReader()` 消费事件，并渲染构建日志、失败详情与复制入口。

- [ ] **Step 2: Run the test to verify it fails**

Run: `venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_sandbox_docker_prebuild_placement_contract.py -q`

Expected: FAIL，因为当前页面只调用普通 POST 并通过 Toast 展示最终结果。

- [ ] **Step 3: Write minimal implementation**

增加日志数组、当前阶段和错误状态；将 `executeDockerPrebuild` 改为带鉴权 header 的 `fetch` SSE 消费，逐条追加日志，成功/失败后保留日志内容。模板中增加可滚动、可复制的日志区，构建期间保留禁用状态。

- [ ] **Step 4: Run the test to verify it passes**

Run: `venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_sandbox_docker_prebuild_placement_contract.py -q`

Expected: PASS。

### Task 4: 聚焦回归验证

**Files:**
- Verify: `app/services/ai/runtime/agentscope/docker_prebuild.py`
- Verify: `app/api/v1/endpoints/sandbox.py`
- Verify: `frontend/src/views/SystemConfig.vue`

- [ ] **Step 1: Run backend and frontend focused tests**

Run: `venv/bin/python -m pytest --confcutdir=tests/frontend tests/ai/runtime/test_docker_prebuild.py tests/api/v1/test_sandbox_connection.py tests/frontend/test_sandbox_docker_prebuild_placement_contract.py tests/frontend/test_sandbox_docker_host_workdir_contract.py`

Expected: all selected tests pass。

- [ ] **Step 2: Run frontend type checking**

Run from `frontend`: `node_modules/.bin/vue-tsc --noEmit`

Expected: exit code 0。

- [ ] **Step 3: Check the diff**

Run: `git diff --check`

Expected: no whitespace errors。不要启动 `./dev.sh`、不要提交或推送。
