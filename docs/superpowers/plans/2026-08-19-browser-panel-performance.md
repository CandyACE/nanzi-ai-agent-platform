# 浏览器面板启动与交互性能优化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让服务端浏览器面板点击后立即可见，并减少重复导航、重复快照、刷新排队和人工点击等待。

**Architecture:** 保持现有“HTTP 创建/恢复会话 + Viewer Token + 单 WebSocket 人工接管”的架构。前端负责立即展示启动状态和合并刷新请求，后端负责复用已打开页面、限制点击等待并在 WebSocket 生命周期结束时释放控制权。

**Tech Stack:** Vue 3 + TypeScript、FastAPI WebSocket、SQLAlchemy async、Playwright、pytest。

---

### Task 1: 建立回归证明

**Files:**
- Modify: `tests/services/ai/test_browser_worker.py`
- Modify: `tests/services/ai/test_browser_runtime.py`
- Modify: `tests/api/v1/test_browser_sessions.py`
- Create: `tests/frontend/test_browser_panel_contract.py`

- [x] **Step 1: 写失败测试**
  - 验证点击没有新页面时不会等待 5 秒，只使用短等待。
  - 验证已有页面 URL 与目标一致时不会再次调用 `goto`。
  - 验证 WebSocket 普通异常路径也调用 `release_human_control`。
  - 验证面板存在立即展开、启动状态、刷新请求去重和断线提示契约。

- [x] **Step 2: 运行定向测试确认失败**

```bash
venv/bin/python -m pytest tests/services/ai/test_browser_worker.py tests/services/ai/test_browser_runtime.py tests/api/v1/test_browser_sessions.py tests/frontend/test_browser_panel_contract.py -q
```

预期：新增行为断言失败，现有测试保持可收集。

### Task 2: 优化后端页面复用与点击响应

**Files:**
- Modify: `app/services/ai/browser/browser_worker.py`
- Modify: `app/services/ai/browser/browser_runtime.py`
- Modify: `app/api/v1/endpoints/browser.py`

- [x] **Step 1: 让 Worker 暴露当前页面信息并短等待点击导航**
  - 复用已有页面时先读取当前 URL；URL 相同直接返回页面信息。
  - 人工 `mouse_click` 的页面加载等待上限从 5000ms 降到 1500ms，保留当前页面继续生成快照的降级行为。

- [x] **Step 2: 保持控制权释放幂等**
  - WebSocket 正常断开和普通异常都走同一个释放流程。
  - 不改变显式“交还 AI”语义。

- [x] **Step 3: 运行后端定向测试**

```bash
venv/bin/python -m pytest tests/services/ai/test_browser_worker.py tests/services/ai/test_browser_runtime.py tests/api/v1/test_browser_sessions.py -q
```

### Task 3: 优化前端启动、首帧和刷新队列

**Files:**
- Modify: `frontend/src/views/EmbedChat.vue`
- Modify: `frontend/src/components/embed/BrowserPanel.vue`
- Modify: `tests/frontend/test_browser_panel_contract.py`

- [x] **Step 1: 立即展示面板**
  - 点击入口先设置面板可见，再异步创建会话和获取 Viewer Token。
  - 添加打开请求状态，防止重复点击发起并发创建请求。
  - 面板无 session/token 时显示阶段性骨架；连接、首帧、失败分别显示明确状态。

- [x] **Step 2: 去掉重复首帧并合并刷新请求**
  - WebSocket 建立后只依赖后端主动发送的首帧。
  - 前端维护快照请求进行状态；进行中时不发送下一次轮询。
  - 关闭连接时清理进行状态，避免卡死。

- [x] **Step 3: 复用已连接会话**
  - 面板从隐藏恢复时，已有 session/token 直接重连 Viewer，不重新调用 `/sessions/open`，也不重新导航页面。

- [x] **Step 4: 运行前端契约和类型检查**

```bash
venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_browser_panel_contract.py -q
cd frontend && npx vue-tsc --noEmit
```

### Task 4: 全量验证与差异审查

- [x] **Step 1: 运行浏览器相关测试**

```bash
venv/bin/python -m pytest tests/services/ai/test_browser_worker.py tests/services/ai/test_browser_runtime.py tests/api/v1/test_browser_sessions.py tests/frontend/test_browser_panel_contract.py -q
```

- [x] **Step 2: 检查差异和工作区边界**

```bash
git diff --check -- app/services/ai/browser/browser_worker.py app/services/ai/browser/browser_runtime.py app/api/v1/endpoints/browser.py frontend/src/components/embed/BrowserPanel.vue frontend/src/views/EmbedChat.vue tests/services/ai/test_browser_worker.py tests/services/ai/test_browser_runtime.py tests/api/v1/test_browser_sessions.py tests/frontend/test_browser_panel_contract.py
git status --short
```

- [x] **Step 3: 汇报验证结果**
  - 只汇报实际执行的测试和检查。
  - 不启动 `./dev.sh`、不部署、不提交代码。
