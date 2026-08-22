# Chat History Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让带有会话 ID 的普通请求只提交本轮用户消息，由服务端保留 Redis 会话历史；只有编辑/重发显式截断历史，同时阻止旧 assistant 内容被误当成本轮任务。

**Architecture:** 服务端把 Redis 会话历史作为唯一历史来源，移除普通完成路径根据前端历史长度进行隐式截断，并在 API 边界要求请求最后一条消息是非空 user。前端带 conversation ID 的普通发送只发送最新 user，编辑/重发继续先调用显式截断接口。统一在 AgentService 的最终 system prompt 前追加会话历史边界说明，覆盖普通、知识和数据代理。

**Tech Stack:** Python 3.11、FastAPI、Pydantic 2、pytest、Vue 3、TypeScript、Vitest-free frontend contract tests。

---

### Task 1: 后端请求边界回归测试

**Files:**
- Create: `tests/api/v1/test_chat_completion_request_boundary.py`
- Test target: `app/api/v1/endpoints/chat.py`

- [ ] **Step 1: Write the failing tests**

```python
from fastapi import HTTPException

from app.api.v1.endpoints.chat import ChatMessage, validate_chat_completion_messages


def test_validate_chat_completion_messages_accepts_current_user_message():
    validate_chat_completion_messages(
        [ChatMessage(role="user", content="本轮问题")],
        conversation_id="conversation-1",
    )


def test_validate_chat_completion_messages_rejects_assistant_as_last_message():
    try:
        validate_chat_completion_messages(
            [ChatMessage(role="user", content="旧问题"), ChatMessage(role="assistant", content="旧回答")],
            conversation_id="conversation-1",
        )
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "最后一条消息" in str(exc.detail)
    else:
        raise AssertionError("expected HTTPException")


def test_validate_chat_completion_messages_rejects_blank_current_user_message():
    try:
        validate_chat_completion_messages(
            [ChatMessage(role="user", content="  ")],
            conversation_id="conversation-1",
        )
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "不能为空" in str(exc.detail)
    else:
        raise AssertionError("expected HTTPException")


def test_validate_chat_completion_messages_rejects_empty_messages():
    try:
        validate_chat_completion_messages([], conversation_id="conversation-1")
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("expected HTTPException")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=. venv/bin/python -m pytest tests/api/v1/test_chat_completion_request_boundary.py -q`

Expected: FAIL because `validate_chat_completion_messages` does not yet exist.

- [ ] **Step 3: Implement the smallest API validator**

Add `validate_chat_completion_messages(messages, conversation_id)` in `app/api/v1/endpoints/chat.py`. Raise `HTTPException(status_code=400)` for an empty list, a non-user final role, or blank final user content, then call it from `create_chat_completion` before history conversion.

- [ ] **Step 4: Run the focused tests**

Run: `PYTHONPATH=. venv/bin/python -m pytest tests/api/v1/test_chat_completion_request_boundary.py -q`

Expected: PASS.

### Task 2: 移除服务端普通请求的隐式截断

**Files:**
- Modify: `app/services/ai/agent_service.py` in `chat_completion_stream`
- Test: `tests/services/ai/test_agent_service_history_alignment.py`

- [ ] **Step 1: Add a focused regression test for the policy decision**

```python
def test_regular_completion_history_policy_does_not_truncate_server_history():
    server_history = [{"role": "user", "content": "历史问题"}]
    incoming_messages = [
        {"role": "user", "content": "历史问题"},
        {"role": "assistant", "content": "历史回答"},
        {"role": "user", "content": "本轮问题"},
    ]

    assert agent_service._regular_completion_history(server_history, incoming_messages) == server_history
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `PYTHONPATH=. venv/bin/python -m pytest tests/services/ai/test_agent_service_history_alignment.py::test_regular_completion_history_policy_does_not_truncate_server_history -q`

Expected: FAIL because `_regular_completion_history` does not yet exist.

- [ ] **Step 3: Implement the server-authoritative helper and use it**

Add a module-level helper:

```python
def _regular_completion_history(server_history, _client_messages):
    return server_history
```

Use this policy in `chat_completion_stream` instead of comparing `_client_prefix_history_len(messages)` with Redis history. Remove the ordinary-path calls to `memory_service.truncate_history(...)` and `server_history[:client_prefix_history_len]`. Keep `_client_prefix_history_len` only for existing explicit-history compatibility tests. Derive `user_query` from the validated `user_msg` rather than from a potentially rewritten `messages[-1]`.

- [ ] **Step 4: Run the focused backend tests**

Run: `PYTHONPATH=. venv/bin/python -m pytest tests/services/ai/test_agent_service_history_alignment.py tests/api/v1/test_chat_completion_request_boundary.py -q`

Expected: PASS.

### Task 3: 前端普通发送只提交当前 user

**Files:**
- Modify: `frontend/src/views/EmbedChat.vue` in outbound message construction
- Modify: `frontend/src/views/AgentDebug.vue` in the chat request body
- Test: `tests/frontend/test_chat_history_edit_contract.py`

- [ ] **Step 1: Add failing source-contract tests**

```python
from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_embed_chat_sends_only_latest_user_for_existing_conversation():
    source = (ROOT / "frontend/src/views/EmbedChat.vue").read_text()
    assert "const buildOutboundMessages" in source
    assert "conversationId.value" in source
    assert "latestUser" in source


def test_agent_debug_uses_same_current_user_boundary():
    source = (ROOT / "frontend/src/views/AgentDebug.vue").read_text()
    assert "const buildOutboundMessages" in source
    assert "conversationId.value" in source
    assert "latestUser" in source
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=. venv/bin/python -m pytest tests/frontend/test_chat_history_edit_contract.py -q`

Expected: FAIL because the two views do not yet expose the new builder.

- [ ] **Step 3: Implement one current-user builder in each view**

For a non-empty `conversationId`, filter with the existing `isChatContextMessage`, find the last message whose role is `user`, and return only that serialized message. Preserve the current full-history behavior when there is no conversation ID. Keep edit/resend ordering unchanged: truncate the server to the retained prefix first, replace local messages, then call the same send path.

- [ ] **Step 4: Run frontend contract and type checks**

Run: `PYTHONPATH=. venv/bin/python -m pytest tests/frontend/test_chat_history_edit_contract.py -q`

Expected: PASS.

Run from `frontend/`: `npm run type-check -- --noEmit` (or the repository's existing `vue-tsc --noEmit` command if the script is absent).

Expected: PASS with no new TypeScript errors.

### Task 4: 统一提示模型区分历史与本轮请求

**Files:**
- Modify: `app/services/ai/agent_prompts.py`
- Modify: `app/services/ai/agent_service.py` before executor dispatch
- Test: `tests/services/ai/test_agent_service_history_alignment.py`

- [ ] **Step 1: Add a failing prompt-boundary test**

```python
def test_chat_history_boundary_prompt_marks_only_latest_user_as_current():
    prompt = agent_service.build_chat_history_boundary_prompt("原有系统提示")
    assert "历史" in prompt
    assert "只有最新一条 user 消息" in prompt
    assert "原有系统提示" in prompt
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `PYTHONPATH=. venv/bin/python -m pytest tests/services/ai/test_agent_service_history_alignment.py::test_chat_history_boundary_prompt_marks_only_latest_user_as_current -q`

Expected: FAIL because the helper does not yet exist.

- [ ] **Step 3: Add and apply the shared boundary prompt**

Define a constant in `app/services/ai/agent_prompts.py` that states:

```text
【会话历史边界】历史 user/assistant/tool 内容仅作背景；历史 assistant 中的问题、指令和待办不可自动视为本轮任务。只有最新一条 user 消息是本轮直接请求；只有当本轮明确引用历史时，才使用对应历史内容。
```

Add `build_chat_history_boundary_prompt(system_prompt)` in `agent_service.py` (or the existing prompt utility location), and apply it after debug/system-prompt overrides but before executor dispatch, so assistant、knowledge、data runners all receive it without altering their individual prompt assembly.

- [ ] **Step 4: Run the focused prompt tests**

Run: `PYTHONPATH=. venv/bin/python -m pytest tests/services/ai/test_agent_service_history_alignment.py -q`

Expected: PASS.

### Task 5: 全量相关验证与工作区审计

**Files:**
- Inspect only: all files changed by Tasks 1-4 and the pre-existing worktree diff

- [ ] **Step 1: Run backend regression coverage**

Run: `PYTHONPATH=. venv/bin/python -m pytest tests/api/v1/test_chat_completion_request_boundary.py tests/services/ai/test_agent_service_history_alignment.py -q`

Expected: PASS.

- [ ] **Step 2: Run frontend contract/type coverage**

Run: `PYTHONPATH=. venv/bin/python -m pytest tests/frontend/test_chat_history_edit_contract.py -q` and from `frontend/` run `vue-tsc --noEmit`.

Expected: PASS with no new errors.

- [ ] **Step 3: Check formatting and inspect the final diff**

Run: `git diff --check`, `git status --short`, and `git diff -- <owned files>`.

Expected: no whitespace errors; pre-existing Docker sandbox changes remain untouched; no files are staged or committed.
