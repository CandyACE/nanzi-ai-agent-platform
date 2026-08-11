# 业务数据确认卡 Implementation Plan

> **For agentic workers:** Execute task-by-task with TDD. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地通用 `request_user_confirmation` 工具 + 可编辑确认卡；点击后以普通用户消息回传指令与字段快照，由模型继续调用写入工具。

**Architecture:** 平台内置只读工具返回结构化 `ui` 载荷；runner 在工具完成时额外下发 SSE `business_confirmation`；前端共享卡片组件编辑后调用现有 `sendMessage` 发回 `【业务确认】…` 文本。不引入批准状态机，不替代 `permission_required`。

**Tech Stack:** Python 3.11 / FastAPI / AgentScope tools / Vue 3 / pytest + frontend contract tests

**Spec:** `docs/superpowers/specs/2026-08-11-business-data-confirmation-design.md`

---

## File map

| File | Responsibility |
|------|----------------|
| `app/services/ai/tools/user_confirmation_tools.py` | 工具实现与入参校验 |
| `app/services/ai/business_confirmation.py` | 解析工具结果 → SSE 载荷；消息正文组装（供测试） |
| `app/services/ai/tools/registry.py` | 注册工具；加入 system implicit |
| `app/services/ai/runtime/agentscope/tools.py` | `READ_ONLY_TOOL_NAMES` |
| `app/services/ai/agent_prompts.py` | one-liner + 意图表 + 业务确认规则段 |
| `app/services/ai/runners/assistant_agent_runner.py` | 工具完成后 yield `business_confirmation` |
| `app/services/ai/runners/chatbi/react_stream.py` | 同上（ChatBI 路径） |
| `frontend/src/utils/businessConfirmation.ts` | 类型、解析、回传消息构建 |
| `frontend/src/utils/agentscopeSseHandlers.ts` | 处理 SSE |
| `frontend/src/components/BusinessConfirmationCard.vue` | 可编辑确认卡 |
| `frontend/src/views/EmbedChat.vue` / `AgentDebug.vue` | 挂载卡片 + 提交发消息 |
| `tests/ai/tools/test_user_confirmation_tool.py` | 工具契约 |
| `tests/frontend/test_business_confirmation_contract.py` | 前端契约 |

---

### Task 1: Backend tool + SSE payload helper

**Files:**
- Create: `app/services/ai/tools/user_confirmation_tools.py`
- Create: `app/services/ai/business_confirmation.py`
- Modify: `registry.py`, `tools.py` (`READ_ONLY_TOOL_NAMES`), `agent_prompts.py`
- Test: `tests/ai/tools/test_user_confirmation_tool.py`

- [ ] **Step 1:** 写失败测试（implicit + read scope + 合法/非法入参 + SSE 解析）
- [ ] **Step 2:** 实现工具与 helper，注册，补提示词
- [ ] **Step 3:** runner 在 tool 完成时 yield `business_confirmation`
- [ ] **Step 4:** pytest 通过后 commit

### Task 2: Frontend card + message builder

**Files:**
- Create: `frontend/src/utils/businessConfirmation.ts`
- Create: `frontend/src/components/BusinessConfirmationCard.vue`
- Modify: `agentscopeSseHandlers.ts`, `EmbedChat.vue`, `AgentDebug.vue`
- Test: `tests/frontend/test_business_confirmation_contract.py`

- [ ] **Step 1:** 写失败契约/行为测试（消息格式、组件存在、SSE handler、视图接线）
- [ ] **Step 2:** 实现 utils + 卡片 + SSE + 双视图接入
- [ ] **Step 3:** 更新 `tests/CHECKLIST.md`
- [ ] **Step 4:** 测试通过后 commit

---

## Out of scope (一期)

- resume API / 后端硬拦写入
- 复杂字段控件
- 历史消息服务端持久化确认状态
