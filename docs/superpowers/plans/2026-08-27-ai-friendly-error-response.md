# AI 友好错误回复与原始错误折叠展示 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. 本次按用户“开发”要求由当前 agent inline 执行，并以测试驱动方式逐项完成。

**Goal:** 将终端执行错误转换成简短、自然、可行动的中文提示；保留脱敏后的原始错误并默认折叠，兼容现有 `type=error/status=error` SSE 协议。

**Architecture:** 后端新增独立的错误呈现服务，负责脱敏、当前模型/备用模型调用、输出校验和静态兜底；`AgentService` 只在终端错误边界调用它，不处理步骤级 `type=log,status=error`。SSE 增加可选 `error_detail`。前端以共享错误归一化工具接收事件，以共享 `ErrorDetailCard` 展示折叠技术详情，EmbedChat 与 AgentDebug 复用同一行为。

**Tech Stack:** Python 3.11, FastAPI/AgentScope runtime, pytest, Vue 3, TypeScript, Vite, Tailwind CSS。

---

## Task 1: 建立后端错误呈现服务的失败测试

**Files:**
- Create: `tests/services/ai/test_error_response_service.py`
- Reference: `app/services/ai/multimodal_support.py`
- Reference: `app/services/ai/config.py`
- Reference: `app/services/ai/runtime/agentscope/chat.py`

- [x] 覆盖普通异常使用当前配置模型生成 1—3 句中文说明，正文不包含原始敏感信息，`error_detail.ai_status` 为 `success`。
- [x] 覆盖当前模型异常/超时后切换备用模型，备用成功时状态为 `fallback`。
- [x] 覆盖模型全部失败、返回空文本或不可接受文本时使用现有 `format_execution_error` 静态兜底。
- [x] 覆盖 `Authorization`、API key、密码、Cookie、数据库凭据和完整内部路径在送入模型及返回详情前均被脱敏/截断。
- [x] 覆盖上下文窗口、多模态不支持、Docker 沙箱不可用等已有专用错误不调用 AI，继续使用稳定的专用提示。

**Verification:** 先运行
`PYTHONPATH=. .venv/bin/python -m pytest -q tests/services/ai/test_error_response_service.py`
并确认因生产模块尚不存在而按预期失败。

## Task 2: 实现后端错误呈现与终端错误接入

**Files:**
- Create: `app/services/ai/error_response_service.py`
- Modify: `app/services/ai/agent_service.py`
- Modify: `tests/services/ai/test_agent_service_turn_status.py` or create a focused agent-service test beside it

- [x] 定义不可变的错误呈现结果，包含 `content`、脱敏后的 `raw_error` 和 `ai_status`（`success`/`fallback`/`disabled`）。
- [x] 复用现有 `AgentConfigProvider.get_configured_llm` 与 `get_fallback_llm`；直接调用 `chat_client_from_handle(...).generate_text(...)`，不传工具，使用短超时。
- [x] 约束错误解释提示词：简体中文、说明发生了什么和下一步、不得猜测，不复述凭据/路径/堆栈；对返回值做空值、长度和格式校验。
- [x] 在 `AgentService` 的多智能体、单智能体 executor 终端错误转发点统一补充 `error_detail`；只识别 `chunk.type == "error"`，不把普通步骤 `type=log,status=error` 送给 AI。
- [x] 顶层异常捕获复用同一呈现服务；呈现服务自身失败时只能走静态兜底，不能递归触发错误解释。
- [x] 保留既有 `type=error`、`status=error`、轮次终态和已知专用错误语义。

**Verification:** 先运行 Task 1 测试确认通过，再运行相关轮次状态测试，确认步骤错误仍不污染终态，终端错误仍为失败。

## Task 3: 建立前端错误事件归一化的失败测试与实现

**Files:**
- Create: `tests/frontend/test_stream_error_presentation.py`
- Create: `frontend/src/utils/streamErrorPresentation.ts`

- [x] 先写契约测试：从 `content/message` 提取用户正文，从 `error_detail.raw_error` 提取原始详情，兼容无详情的旧 SSE。
- [x] 定义共享类型 `StreamErrorDetail`，前端使用 camelCase，但明确映射后端的 `error_detail/raw_error/ai_status`。
- [x] 提供应用函数，将错误写入消息时统一追加 `❌ 处理未完成`；相同事件重复经过 dispatch/status 分支时不得重复追加。
- [x] 对缺失内容使用“未知错误”，对非字符串 payload 安全降级。

**Verification:** 先运行前端契约测试并确认红灯，再实现工具后确认绿灯。

## Task 4: 创建折叠技术详情组件并接入两类聊天消息

**Files:**
- Create: `frontend/src/components/chat/ErrorDetailCard.vue`
- Modify: `frontend/src/views/EmbedChat.vue`
- Modify: `frontend/src/views/AgentDebug.vue`
- Add/modify frontend contract tests under `tests/frontend/`

- [x] 先补组件契约：原始错误默认隐藏，使用原生 `<details>`/`<summary>`；展开后原文使用文本节点展示，避免被 Markdown/HTML 执行；提供复制按钮并复用 `frontend/src/utils/clipboard.ts`。
- [x] 组件显示“查看技术详情”，复制成功后给出短暂状态反馈；无原始错误时不渲染空卡片。
- [x] 两个页面的 Message 类型增加可选 `errorDetail`，错误分支统一调用共享归一化工具，移除散落的 `服务异常` 硬编码拼接。
- [x] 主正文显示固定标题“处理未完成”和 AI 生成的说明；正文下方渲染折叠技术详情，避免同一错误重复出现。
- [x] 保留等待、取消、权限恢复、普通日志和正常回答的现有行为；不对步骤级日志错误渲染终端错误卡。

**Verification:** 运行前端契约测试；再执行 `cd frontend && npm run build`（不启动开发服务），修复本次新增文件引入的类型/模板错误。

## Task 5: 更新测试清单并执行聚焦回归

**Files:**
- Modify: `tests/CHECKLIST.md`

- [x] 增加“AI 友好错误回复与原始错误折叠展示”条目，列明后端模型成功/备用/静态兜底、脱敏、步骤错误不触发，以及两页面折叠/复制契约。
- [x] 运行后端错误服务、AgentService 状态及相关现有 AI 测试。
- [x] 运行前端错误工具、消息渲染和相关 SSE/UI 契约测试。
- [x] 运行 `git diff --check`，检查 `git status --short`，确认只包含本次文件和用户已有的无关改动；不自动 stage/commit。
- [x] 最终报告静态测试结果与尚未执行的真实模型、浏览器和服务环境验收，并提醒用户自行运行 `./dev.sh`。

## Notes on implementation boundaries

- 不修改数据库、不新增迁移、不改变模型选择配置页面。
- AI 错误解释必须是有界的辅助调用，任何超时、异常、空响应和敏感内容校验失败均回退到既有静态错误格式。
- `error_detail.raw_error` 只能是脱敏后的短文本；堆栈、请求头、密钥、Cookie、密码、数据库连接串和完整绝对路径不得进入 SSE 或持久化回答。
- 实现阶段遵守仓库现有未提交改动，不执行 `./dev.sh`、部署脚本或生产数据库操作。
