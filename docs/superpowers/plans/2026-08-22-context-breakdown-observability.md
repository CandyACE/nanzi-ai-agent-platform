# 上下文分项 Token 可观测性 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在实际模型调用统计和输入框上下文详情中展示系统提示词、工具 schema、对话消息三类 Token 分项。

**Architecture:** 在 AgentScope middleware 中按同一 `count_tokens(messages, tools)` 口径计算分项，写入现有 Redis 模型调用记录。前端 `useContextUsage` 并行读取上下文总量和最近一次模型调用记录，模型调用弹窗直接消费单条统计，输入框弹层消费最近一次分项。

**Tech Stack:** Python 3.11、FastAPI/Pydantic 2、AgentScope 2.0.6、Vue 3、TypeScript、pytest、vue-tsc。

---

### Task 1: 建立后端分项计数契约

**Files:**
- Create: `app/services/ai/runtime/agentscope/context_breakdown.py`
- Test: `tests/ai/test_model_call_context_breakdown.py`

- [x] **Step 1: Write the failing test**

增加测试：构造 system、user、assistant、tool 消息和两个工具 schema，使用 fake model 返回输入计数，断言返回 `system_prompt_tokens`、`tools_tokens`、`conversation_tokens`、`total_tokens`，并且三项之和等于总量。

- [x] **Step 2: Run the test to verify it fails**

运行：`venv/bin/python -m pytest tests/ai/test_model_call_context_breakdown.py -q`

预期：因 `context_breakdown` 模块或函数不存在而失败。

- [x] **Step 3: Write the minimal implementation**

实现异步 helper：调用模型分别统计完整请求、system 消息和工具 schema；将剩余 Token 归入非 system 对话消息；计数异常返回空分项，不向上抛出阻断模型调用。

- [x] **Step 4: Run the test to verify it passes**

运行同一命令，预期测试通过。

### Task 2: 将分项写入模型调用统计和 API

**Files:**
- Modify: `app/services/ai/runtime/agentscope/middleware.py:362-530`
- Modify: `app/api/v1/endpoints/chat.py:855-888`
- Test: `tests/ai/test_model_call_context_breakdown.py`

- [x] **Step 1: Write the failing test**

扩展 middleware 测试，fake model 返回可区分的计数，执行 `on_model_call`，断言 `_append_stat_to_redis` 收到的 record 含 `context_breakdown`；再覆盖计数异常时模型仍执行并写入空分项。

- [x] **Step 2: Run the test to verify it fails**

运行：`venv/bin/python -m pytest tests/ai/test_model_call_context_breakdown.py -q`

预期：record 尚无 `context_breakdown` 字段而失败。

- [x] **Step 3: Write the minimal implementation**

在 middleware 进入模型调用前计算分项，把结果放入 `record_base`；在 API Pydantic 模型中声明兼容的嵌套字段，保留旧 Redis 记录缺少该字段时的默认空值。

- [x] **Step 4: Run the test to verify it passes**

运行：`venv/bin/python -m pytest tests/ai/test_model_call_context_breakdown.py tests/api/v1/test_chat_context_usage.py -q`

预期全部通过。

### Task 3: 接入前端统计类型和模型调用弹窗

**Files:**
- Modify: `frontend/src/components/chat/ChatModelCallStatsModal.vue`
- Modify: `tests/frontend/test_chat_model_call_stats_context_contract.py`

- [x] **Step 1: Write the failing test**

增加契约断言，要求弹窗出现系统提示词、工具 schema、对话消息、估算标识和分项字段名。

- [x] **Step 2: Run the test to verify it fails**

运行：`venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_chat_model_call_stats_context_contract.py -q`

预期：当前弹窗没有分项字段而失败。

- [x] **Step 3: Write the minimal implementation**

在现有上下文窗口区域下增加三行分项进度/数值，旧记录无 breakdown 时不显示；使用统一的 Token 格式化函数，并标注“估算”。

- [x] **Step 4: Run the test to verify it passes**

运行同一命令，预期通过。

### Task 4: 将最近一次分项接入输入框详情

**Files:**
- Modify: `frontend/src/composables/useContextUsage.ts`
- Modify: `frontend/src/components/embed/ChatInput.vue`
- Modify: `tests/frontend/test_chat_context_usage_contract.py`

- [x] **Step 1: Write the failing test**

增加契约断言：composable 请求 `/model_calls` 并暴露最近一次 breakdown；输入框弹层展示“最近一次实际请求”和三类分项。

- [x] **Step 2: Run the test to verify it fails**

运行：`venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_chat_context_usage_contract.py -q`

预期：当前 composable 和弹层没有这些字段而失败。

- [x] **Step 3: Write the minimal implementation**

在 `refreshContextUsage` 中并行读取上下文接口和模型调用接口，模型调用接口失败时不影响原上下文展示；按返回顺序取最近一条统计，将 breakdown 挂到 ContextUsage。输入框在现有详情中新增最近一次实际请求明细。

- [x] **Step 4: Run the test to verify it passes**

运行：`venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_chat_context_usage_contract.py -q`

预期通过。

### Task 5: 全量聚焦验证

**Files:**
- Test: `tests/ai/test_model_call_context_breakdown.py`, `tests/api/v1/test_chat_context_usage.py`, `tests/frontend/test_chat_model_call_stats_context_contract.py`, `tests/frontend/test_chat_context_usage_contract.py`

- [x] **Step 1: Run focused regression tests**

运行：`venv/bin/python -m pytest tests/ai/test_model_call_context_breakdown.py tests/api/v1/test_chat_context_usage.py tests/ai/test_model_call_context_guard.py -q` 以及前端两个契约测试。

- [x] **Step 2: Run static checks**

运行：`venv/bin/python -m compileall -q app`、`cd frontend && node_modules/.bin/vue-tsc --noEmit`、`git diff --check`。

- [x] **Step 3: Inspect scope**

    运行：`git status --short` 和 `git diff --stat`，确认不包含用户已有的 `docs/release/1.0.12/`，不执行提交。

### Task 6: 将会话整体构成接入总量接口和总图条

**Files:**
- Modify: `app/services/ai/context_usage.py`
- Modify: `frontend/src/composables/useContextUsage.ts`
- Modify: `frontend/src/components/embed/ChatInput.vue`
- Test: `tests/ai/tools/test_context_usage_service.py`
- Test: `tests/frontend/test_chat_context_usage_contract.py`

- [x] **Step 1: Write the failing test**

增加后端测试：Redis 历史消息估算为 40，最近运行记录的系统提示词为 3、工具为 11，断言整体总量为 54，且固定开销只合并一次。增加前端契约断言，要求总图条存在三段构成和“会话整体构成”明细。

- [x] **Step 2: Run tests to verify they fail**

运行：

```bash
venv/bin/python -m pytest tests/ai/tools/test_context_usage_service.py::test_context_usage_aggregates_session_breakdown_without_repeating_runtime_overhead -q
venv/bin/python -m pytest --confcutdir=tests/frontend tests/frontend/test_chat_context_usage_contract.py -q
```

预期：后端缺少整体构成字段，前端缺少总图条分段契约。

- [x] **Step 3: Implement the minimal aggregation and display**

共享上下文服务读取最近模型统计中的 system/tool 固定开销，与完整会话历史估算合并一次，重新计算 `estimated_current_tokens`、剩余量和百分比，并返回 `context_breakdown`。输入框使用该整体字段把已用宽度分为系统提示词、工具 schema、对话消息三段，同时保留最近一次模型请求明细作为对照。

- [x] **Step 4: Run focused verification**

运行后端上下文测试、前端契约测试、`venv/bin/python -m compileall -q app`、从 `frontend/` 执行 `node_modules/.bin/vue-tsc --noEmit` 和 `git diff --check`，预期全部通过。
