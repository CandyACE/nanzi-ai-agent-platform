# `ask_user_question` Trigger Optimization Implementation Plan

> **For agentic workers:** Implement this plan task-by-task with TDD. Keep unrelated worktree changes intact and do not commit unless explicitly requested.

**Goal:** 让通用助手与知识库助手在用户明确要求互动式提问时稳定促发 `ask_user_question`，同时保留任务澄清的严格边界。

**Architecture:** 在 `tool_nudge_policy.py` 中增加无 LLM 的显式互动意图识别与专用 `ToolNudge`。通用助手复用现有 Tool Preflight 强制首步调用；知识库助手在知识库预检索完成后复用同一识别结果，将首步工具选择传给现有 AgentScope 执行器。平台提示词和工具描述同步表达主动互动、决策收集、任务澄清三类模式。

**Tech Stack:** Python 3.11, pytest, AgentScope Runtime, FastAPI SSE, Redis pending question protocol.

---

### Task 1: Add failing tests for explicit interactive intent

**Files:**
- Modify: `tests/ai/test_tool_nudge_policy.py`
- Test: `app/services/ai/tool_nudge_policy.py`

- [x] Add positive cases for “随便问我几个问题”“考考我”“我不知道怎么提问，你引导我”“先问我几个问题再帮我规划”“一个一个问我”。
- [x] Add negative cases for “给我列几个问题”“不要问我，直接回答”“不用提问”。
- [x] Add a test that `resolve_tool_nudge()` returns a forced `ask_user_question` nudge only when that tool is present.
- [x] Run the focused policy tests first and confirm the new tests fail before implementation.

### Task 2: Implement the shared explicit interaction nudge

**Files:**
- Modify: `app/services/ai/tool_nudge_policy.py`

- [x] Add normalized positive and negative phrase groups and `looks_like_explicit_user_question_request(query)`.
- [x] Add `_resolve_explicit_user_question_nudge(query, tools)` that returns a score-1.0, `force_first_call=True` nudge for `ask_user_question` only when the tool is available.
- [x] Run the focused policy tests and verify all new positive/negative cases pass.

### Task 3: Wire the nudge into the general assistant preflight

**Files:**
- Modify: `app/services/ai/runners/assistant_agent_runner.py`
- Modify: `tests/ai/test_tool_nudge_policy.py` only if a preflight integration assertion is needed

- [x] Evaluate the explicit interaction nudge before generic relevance matching and before unrelated tool nudges.
- [x] Preserve the existing no-nudge path for `memory_search`, greetings, automatic delivery, and explicit cancellation/receipt messages.
- [x] Reuse the existing `ToolChoice` wrapper and `force_first_call` path; do not add a second model invocation or a new execution loop.
- [x] Run the focused assistant/tool-preflight tests and verify the existing delegation, notification, and todo nudge tests remain green.

### Task 4: Wire the nudge into the knowledge-agent path

**Files:**
- Modify: `app/services/ai/runners/knowledge_agent_runner.py`
- Test: `tests/ai/runners/test_knowledge_agent_tools.py` or a focused new test under `tests/ai/runners/`

- [x] After the existing knowledge prefetch/reuse setup and before the first AgentScope execution, resolve the shared explicit interaction nudge.
- [x] Prepend the nudge message to `current_system_content` and pass a first-call `ToolChoice` for `ask_user_question` into `_execute_with_agentscope_native_agent`.
- [x] Keep knowledge retrieval before the question when the user asks to be quizzed on documents, and keep citation/grounding guards unchanged.
- [x] Add focused knowledge-runner tests for explicit interactive input, ordinary question listing, and automatic delivery.

### Task 5: Align prompt and tool contracts

**Files:**
- Modify: `app/services/ai/agent_prompts.py`
- Modify: `app/services/ai/tools/user_question_tools.py`
- Modify: `tests/ai/tools/test_user_question_tool.py`
- Modify: `tests/ai/test_prompt_assembler.py`

- [x] Add explicit priority language: user-requested interaction first, important decision collection second, blocking clarification third, safe inference otherwise.
- [x] Add positive and negative examples and state that “列出问题” is not the same as “逐个问我”。
- [x] Keep one-question-per-turn, pending ownership, cancellation, business confirmation separation, and automatic-task restrictions.
- [x] Assert the assembled prompt and tool description contain the new contract.

### Task 6: Verification and handoff

**Files:**
- Modify: `tests/CHECKLIST.md`

- [x] Run the focused policy, prompt, tool-contract, and knowledge-agent tests.
- [x] Run Python compilation and `git diff --check` on the scoped changes.
- [x] Do not run `./dev.sh`, deployment scripts, or services; runtime console validation remains for the user.
- [x] Do not stage or commit unless the user explicitly requests it.
