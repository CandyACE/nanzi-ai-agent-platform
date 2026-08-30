# Unified Reusable Result Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 统一保存普通工具和子代理的可交付结果，并在后续请求中由服务端优先复用，命中时避免重复执行，未命中时回退现有路由和查询逻辑。

**Architecture:** 在 `MemoryService` 之上增加统一 reusable-result 规范和 Redis current/stack 存储，在公共 AgentService/Runner 边界增加结果解析与读取决策。普通工具和 `sub_agent_call` 通过同一候选保存入口写入主会话；`history` 保持独立，现有 ChatBI 与 `session_tool_artifact` 通过兼容读取继续工作。快捷按钮发送的 `【被点击的 AI 回复】` 标记在路由前识别为优先复用意图，但缓存缺失、过期或不足时继续现有路由/查询回退。

**Tech Stack:** Python 3.11, FastAPI, async Redis, Pydantic 2, pytest, 现有 AgentScope Runner/Router。

---

## 文件结构

- Create: `app/services/ai/reusable_result.py` — 统一结果字段、结果类型、复用意图和纯函数选择逻辑。
- Modify: `app/services/ai/memory_service.py` — `reusable_result_v1` current/stack 的 key、读写、幂等追加和清理。
- Modify: `app/services/ai/session_tool_artifact.py` — 将现有通用快照转换为兼容适配层，并复用统一的结果判断/提示格式。
- Modify: `app/services/ai/agent_service.py` — 在路由前加载 reusable result 复用决策，并把决策传给执行上下文。
- Modify: `app/services/ai/router_service.py` / `app/services/ai/turn_decision.py` — 增加复用命中、未命中回退和来源元数据，不改变普通新请求的路由。
- Modify: `app/services/ai/runners/assistant_agent_runner.py` — 统一注入可复用结果、轮末保存结果和记录 fallback 原因。
- Modify: `app/services/ai/runners/data_agent_runner.py` / `app/services/ai/runners/chatbi/followup_data.py` — 将 ChatBI 结果接入统一来源，同时保留旧 key 双写/兼容读取。
- Modify: `app/services/ai/tools/agent_delegate_tool.py` — 确保主会话能够捕获成功子代理/批量子代理的交付结果，不直接破坏子会话隔离。
- Create: `tests/ai/test_reusable_result.py` — 统一结果规范、候选判断、复用意图和选择器测试。
- Modify: `tests/services/ai/test_memory_service.py` / `tests/ai/test_chatbi_result_stack.py` — Redis key、current/stack、TTL 和清理测试。
- Modify: `tests/ai/test_session_tool_artifact.py` — 兼容快照与新 reusable result 的行为测试。
- Create: `tests/ai/test_reusable_result_routing.py` — 快捷操作命中/未命中/刷新回退的路由契约测试。
- Create: `tests/ai/runners/test_assistant_agent_reusable_result.py` — Assistant Runner 的 Prompt 注入、轮末持久化和中断行为。
- Modify: `tests/ai/test_sub_agent_delegation.py` — 子代理结果被主会话捕获且失败结果不覆盖的测试。

### Task 1: Define the reusable-result contract

**Files:**
- Create: `app/services/ai/reusable_result.py`
- Create: `tests/ai/test_reusable_result.py`

- [ ] **Step 1: Write failing pure-function tests**

Add tests for the public functions that will define the contract:

```python
def test_build_reusable_result_keeps_origin_and_safe_content():
    result = build_reusable_result(
        tool_name="sub_agent_call",
        tool_output={"answer": "方案正文"},
        source_type="system",
        tool_args={"token": "secret", "agent_name": "knowledge-agent"},
        user_question="请查手册",
        trace_id="trace-1",
        origin_type="sub_agent",
    )
    assert result["result_type"] == "knowledge"
    assert result["origin_type"] == "sub_agent"
    assert result["origin_name"] == "sub_agent_call"
    assert result["structured"] == {"answer": "方案正文"}
    assert result["tool_args"]["token"] == "[redacted]"


def test_reuse_decision_prefers_existing_result_but_allows_fallback_when_missing():
    hit = resolve_reusable_result("请基于刚才结果生成报告", current={"result_id": "r1", "result_type": "generic"}, stack=[])
    miss = resolve_reusable_result("请基于刚才结果生成报告", current=None, stack=[])
    assert hit.mode == "reuse"
    assert hit.result["result_id"] == "r1"
    assert miss.mode == "fallback"


def test_refresh_request_bypasses_existing_result():
    decision = resolve_reusable_result(
        "请重新查询最新数据",
        current={"result_id": "r1", "result_type": "data"},
        stack=[],
    )
    assert decision.mode == "fallback"
    assert decision.reason == "freshness_requested"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/bin/python -m pytest tests/ai/test_reusable_result.py -q`

Expected: FAIL because `app.services.ai.reusable_result` and its contract functions do not exist.

- [ ] **Step 3: Implement the minimal contract**

Implement JSON-safe result construction with these invariants:

```python
RESULT_TYPES = frozenset({"data", "knowledge", "web", "file", "code", "generic"})

@dataclass(frozen=True)
class ReusableResultDecision:
    mode: Literal["none", "reuse", "fallback"]
    result: dict[str, Any] | None = None
    reason: str = ""

def build_reusable_result(
    *,
    tool_name: str,
    tool_output: Any,
    source_type: str,
    tool_args: Mapping[str, Any] | None,
    user_question: str,
    trace_id: str | None,
    origin_type: str | None = None,
) -> dict[str, Any]:
    # normalize text/structured output, classify result_type, redact args,
    # truncate content, and set origin/status/timestamps.

def resolve_reusable_result(user_question, *, current, stack):
    # explicit refresh words always return fallback;
    # result/context references return reuse only with a valid candidate;
    # result absence or insufficiency returns fallback rather than an error.
```

Do not read Redis or call a model from this module. Keep type classification, refresh detection, marker detection, result-size limits, and candidate selection deterministic and directly testable.

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/bin/python -m pytest tests/ai/test_reusable_result.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the contract**

```bash
git add app/services/ai/reusable_result.py tests/ai/test_reusable_result.py
git commit -m "feat: 定义通用可复用结果协议"
```

### Task 2: Add current/stack Redis persistence

**Files:**
- Modify: `app/services/ai/memory_service.py`
- Modify: `tests/services/ai/test_memory_service.py`
- Modify: `tests/ai/test_chatbi_result_stack.py`

- [ ] **Step 1: Write failing storage tests**

Cover exact keys, replacement/append behavior, idempotency, TTL, isolation, and cleanup:

```python
@pytest.mark.asyncio
async def test_reusable_result_current_and_stack_use_user_conversation_scope(monkeypatch):
    redis = _FakeRedis()
    monkeypatch.setattr("app.services.ai.memory_service.get_redis", AsyncMock(return_value=redis))
    service = MemoryService()
    first = {"result_id": "r1", "result_type": "generic", "status": "completed"}
    second = {"result_id": "r2", "result_type": "file", "status": "completed"}
    await service.set_reusable_result("u1", "c1", first)
    await service.push_reusable_result("u1", "c1", second)

    assert (await service.get_reusable_result("u1", "c1"))["result_id"] == "r2"
    assert [item["result_id"] for item in await service.get_reusable_result_stack("u1", "c1")] == ["r1", "r2"]
    assert "conversation:u1:c1:reusable_result_v1:current" in redis.values
    assert "conversation:u1:c1:reusable_result_v1:stack" in redis.values


@pytest.mark.asyncio
async def test_reusable_result_push_is_idempotent_and_cleanup_removes_both_keys(monkeypatch):
    redis = _FakeRedis()
    monkeypatch.setattr("app.services.ai.memory_service.get_redis", AsyncMock(return_value=redis))
    service = MemoryService()
    result = {"result_id": "same", "result_type": "generic", "status": "completed"}
    await service.push_reusable_result("u1", "c1", result)
    await service.push_reusable_result("u1", "c1", result)
    await service.clear_history("u1", "c1")
    assert "conversation:u1:c1:reusable_result_v1:current" not in redis.values
    assert "conversation:u1:c1:reusable_result_v1:stack" not in redis.values
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/bin/python -m pytest tests/services/ai/test_memory_service.py tests/ai/test_chatbi_result_stack.py -q`

Expected: FAIL because the unified methods and keys do not exist.

- [ ] **Step 3: Implement MemoryService storage**

Add `_get_reusable_result_key()` and `_get_reusable_result_stack_key()` using `require_user_id()`. Implement JSON read/write with `self.ttl`; `push_reusable_result()` must deduplicate by `result_id`, retain the newest 10 entries, set `current` to the pushed result, and preserve user/conversation scope. Extend `clear_history()` to delete both keys.

Use the existing Redis test doubles and keep Redis failures non-blocking: reads return `None`/`[]`, writes log and return without raising.

- [ ] **Step 4: Run storage tests**

Run: `./.venv/bin/python -m pytest tests/services/ai/test_memory_service.py tests/ai/test_chatbi_result_stack.py -q`

Expected: PASS, with existing ChatBI stack tests unchanged.

- [ ] **Step 5: Commit storage**

```bash
git add app/services/ai/memory_service.py tests/services/ai/test_memory_service.py tests/ai/test_chatbi_result_stack.py
git commit -m "feat: 增加可复用结果会话缓存"
```

### Task 3: Unify tool and sub-agent result candidates

**Files:**
- Modify: `app/services/ai/session_tool_artifact.py`
- Modify: `app/services/ai/runners/assistant_agent_runner.py`
- Modify: `app/services/ai/tools/agent_delegate_tool.py`
- Modify: `tests/ai/test_session_tool_artifact.py`
- Modify: `tests/ai/test_sub_agent_delegation.py`

- [ ] **Step 1: Write failing candidate and persistence tests**

Add tests proving all of the following:

```python
def test_sub_agent_result_is_a_generic_reusable_candidate():
    turn = {"user_question": "调用知识助手", "trace_id": "t1", "best": None}
    consider_turn_artifact_candidate(
        turn,
        tool_name="sub_agent_call",
        tool_args={"agent_name": "knowledge-agent"},
        tool_output="这是子代理返回的可交付方案正文。" * 20,
        source_type="system",
        permission_scope="read",
    )
    assert turn["best"]["origin_type"] == "sub_agent"
    assert turn["best"]["result_type"] in {"knowledge", "generic"}


@pytest.mark.asyncio
async def test_persist_candidate_writes_unified_result_and_legacy_compatibility(monkeypatch):
    from app.services.ai.session_tool_artifact import persist_turn_artifact_candidate

    unified = AsyncMock()
    legacy = AsyncMock()
    stack = AsyncMock()
    monkeypatch.setattr("app.services.ai.memory_service.memory_service.set_reusable_result", unified)
    monkeypatch.setattr("app.services.ai.memory_service.memory_service.push_reusable_result", stack)
    monkeypatch.setattr("app.services.ai.memory_service.memory_service.set_session_tool_artifact", legacy)
    await persist_turn_artifact_candidate(
        user_id="7",
        conversation_id="conv-1",
        turn_state={
            "user_question": "调用知识助手",
            "trace_id": "trace-1",
            "best": {
                "result_id": "result-1",
                "result_type": "knowledge",
                "origin_type": "sub_agent",
                "origin_name": "sub_agent_call",
                "status": "completed",
                "content": "知识助手返回的方案正文",
                "structured": None,
            },
        },
    )
    unified.assert_awaited_once()
    stack.assert_awaited_once()
    legacy.assert_awaited_once()
```

Also test a failed/empty/cancelled child result does not replace an existing successful current result, while a normal no-candidate turn still clears the legacy current snapshot according to the confirmed policy.

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `./.venv/bin/python -m pytest tests/ai/test_session_tool_artifact.py tests/ai/test_sub_agent_delegation.py -q`

Expected: FAIL on missing unified payload fields and persistence calls.

- [ ] **Step 3: Implement unified candidate conversion**

Refactor `build_artifact_payload()`/`consider_turn_artifact_candidate()` to build the canonical reusable-result payload while preserving legacy fields (`tool_name`, `text_excerpt`, `structured`, `saved_at`) for old prompt and tests. Infer `origin_type="sub_agent"` for `sub_agent_call` and `sub_agent_batch_call`; keep excluded tools excluded unless they produce an explicit deliverable path.

At normal turn finalization, persist the canonical result to `current` and `stack`, then write the legacy `session_tool_artifact_v1` compatibility payload. On interruption with no candidate, do not delete the unified or legacy current result. On normal completion with no candidate, delete only the current snapshot and keep the still-valid stack.

Do not let a child write the parent key directly from its isolated context. The parent’s tool-observation/persistence boundary is the only place that promotes the returned child result.

- [ ] **Step 4: Run focused tests**

Run: `./.venv/bin/python -m pytest tests/ai/test_session_tool_artifact.py tests/ai/test_sub_agent_delegation.py -q`

Expected: PASS.

- [ ] **Step 5: Commit candidate integration**

```bash
git add app/services/ai/session_tool_artifact.py app/services/ai/runners/assistant_agent_runner.py app/services/ai/tools/agent_delegate_tool.py tests/ai/test_session_tool_artifact.py tests/ai/test_sub_agent_delegation.py
git commit -m "feat: 统一保存工具与子代理结果"
```

### Task 4: Add server-side result resolution and prompt injection

**Files:**
- Modify: `app/services/ai/reusable_result.py`
- Modify: `app/services/ai/agent_service.py`
- Modify: `app/services/ai/router_service.py`
- Modify: `app/services/ai/turn_decision.py`
- Modify: `app/services/ai/runners/assistant_agent_runner.py`
- Create: `tests/ai/test_reusable_result_routing.py`

- [ ] **Step 1: Write failing routing tests**

Test the three required paths:

```python
def test_clicked_reply_marker_is_reuse_first_not_new_query():
    decision = resolve_reusable_result(
        "请生成报告\n\n---\n\n【被点击的 AI 回复】\n已有结论",
        current={"result_id": "r1", "result_type": "generic", "content": "已有结论"},
        stack=[],
    )
    assert decision.mode == "reuse"
    assert decision.reason == "clicked_reply_context"


def test_clicked_reply_without_cache_returns_existing_fallback_mode():
    decision = resolve_reusable_result(
        "请生成可视化分析报告\n\n---\n\n【被点击的 AI 回复】\n已有表格",
        current=None,
        stack=[],
    )
    assert decision.mode == "fallback"
    assert decision.reason == "result_unavailable"


def test_fresh_request_never_injects_old_result():
    decision = resolve_reusable_result(
        "请重新查询最新数据",
        current={"result_id": "r1", "result_type": "data"},
        stack=[],
    )
    assert decision.mode == "fallback"
    assert decision.result is None
```

Add an integration-level assertion that a reuse hit causes no `sub_agent_call`/SQL dispatch request, while a miss leaves the existing route/dispatcher eligible. Use the repository’s no-infrastructure fixtures and mocks only at the route/dispatch seam.

- [ ] **Step 2: Run routing tests to verify they fail**

Run: `./.venv/bin/python -m pytest tests/ai/test_reusable_result_routing.py -q`

Expected: FAIL because route decisions do not carry reusable-result state and the common runner still only reads the legacy artifact.

- [ ] **Step 3: Implement resolver and route metadata**

Load current/stack once per request using `user_id + conversation_id`. Add a small internal reusable-result decision field to the existing route/turn state rather than exposing a new public model tool. The decision must distinguish:

```text
none       无引用信号或无会话
reuse      命中且结果足够，优先复用
fallback   缺失/过期/不足/明确刷新，走现有逻辑
```

Detect the existing `【被点击的 AI 回复】` marker before generic routing. On `reuse`, inject a bounded `[可复用结果]` block and prevent the router from selecting the original data/knowledge/sub-agent acquisition path solely because the embedded reply contains data words. On `fallback`, preserve current route selection and tool availability; emit only internal trace metadata indicating why reusable-result reuse was not used.

Reuse decisions must not bypass explicit user agent selection, permission checks, or fresh-data requests. Redis failures return `fallback` and never fail the request.

- [ ] **Step 4: Implement common prompt injection**

Replace the Assistant runner’s direct legacy-only load with a compatibility sequence:

```python
unified = await load_reusable_result(user_id, conversation_id)
if unified is None:
    unified = await load_legacy_session_tool_artifact(user_id, conversation_id)
decision = resolve_reusable_result(user_query, current=unified, stack=stack)
system_content = append_reusable_result_to_prompt(system_content, decision)
```

Keep the prompt bounded; include result type, source, timestamp, status, excerpt/structured preview, and explicit instruction that the result is reusable context rather than a fresh fact. Do not inject on greetings, unrelated new topics, or explicit refresh requests.

- [ ] **Step 5: Run routing and runner tests**

Run: `./.venv/bin/python -m pytest tests/ai/test_reusable_result.py tests/ai/test_reusable_result_routing.py tests/ai/test_session_tool_artifact.py tests/ai/runners/test_assistant_agent_reusable_result.py -q`

Expected: PASS for the focused set.

- [ ] **Step 6: Commit route/injection integration**

```bash
git add app/services/ai/reusable_result.py app/services/ai/agent_service.py app/services/ai/router_service.py app/services/ai/turn_decision.py app/services/ai/runners/assistant_agent_runner.py tests/ai/test_reusable_result_routing.py tests/ai/test_reusable_result.py
git commit -m "feat: 优先复用会话结果并保留查询回退"
```

### Task 5: Preserve ChatBI compatibility and cleanup behavior

**Files:**
- Modify: `app/services/ai/runners/chatbi/followup_data.py`
- Modify: `app/services/ai/runners/data_agent_runner.py`
- Modify: `app/services/ai/memory_service.py`
- Modify: `tests/ai/test_chatbi_result_stack.py`
- Modify: `tests/services/ai/test_memory_service.py`

- [ ] **Step 1: Write failing compatibility tests**

Add tests that ChatBI success writes the unified result while still writing `last_data_result`/`data_result_stack_v1`, that unified reads win when present, and that old ChatBI keys are used when the unified keys are absent. Add a test that `clear_history()` removes all three result representations without deleting unrelated user sessions.

- [ ] **Step 2: Run compatibility tests to verify they fail**

Run: `./.venv/bin/python -m pytest tests/ai/test_chatbi_result_stack.py tests/services/ai/test_memory_service.py -q`

Expected: FAIL on missing dual-write/compatibility behavior.

- [ ] **Step 3: Implement compatibility adapter**

Keep ChatBI’s structured `ChatBIResultRef` as a valid `result_type="data"` reusable result. Preserve its existing parent-result semantics and max depth. Use the unified resolver for generic selection but retain the old data-agent fast path and legacy dual-write until all readers are migrated.

- [ ] **Step 4: Run compatibility tests**

Run: `./.venv/bin/python -m pytest tests/ai/test_chatbi_result_stack.py tests/services/ai/test_memory_service.py -q`

Expected: PASS.

- [ ] **Step 5: Commit compatibility**

```bash
git add app/services/ai/runners/chatbi/followup_data.py app/services/ai/runners/data_agent_runner.py app/services/ai/memory_service.py tests/ai/test_chatbi_result_stack.py tests/services/ai/test_memory_service.py
git commit -m "feat: 保留ChatBI结果缓存兼容"
```

### Task 6: Regression validation and review

**Files:**
- Modify only if tests reveal a scoped regression.

- [ ] **Step 1: Run focused backend regression**

Run:

```bash
./.venv/bin/python -m pytest \
  tests/ai/test_reusable_result.py \
  tests/ai/test_reusable_result_routing.py \
  tests/ai/test_session_tool_artifact.py \
  tests/ai/test_chatbi_result_stack.py \
  tests/services/ai/test_memory_service.py \
  tests/ai/test_sub_agent_delegation.py -q
```

Expected: all selected tests pass. Redis-dependent failures must be separated from logic failures and reported as infrastructure limitations.

- [ ] **Step 2: Run static checks**

Run:

```bash
./.venv/bin/python -m compileall -q app/services/ai
git diff --check
```

Expected: both commands exit successfully.

- [ ] **Step 3: Verify behavior boundaries manually from tests/log contracts**

Confirm the test evidence covers:

- current replacement versus stack retention;
- user/conversation isolation;
- 30-day Redis TTL and business `expires_at`/`requires_fresh` rejection;
- generic tool and child-agent promotion;
- shortcut reuse hit with no duplicate query/delegation;
- cache miss/insufficient result fallback to existing query behavior;
- explicit latest/refresh bypass;
- interruption retention and normal no-candidate cleanup;
- ChatBI legacy compatibility;
- Redis failure non-blocking behavior.

- [ ] **Step 4: Request code review before delivery**

Use the requesting-code-review workflow against the implementation range. Include the design document, focused test output, and the explicit duplicate-execution acceptance criteria in the reviewer prompt. Fix Critical and Important findings before final delivery.

- [ ] **Step 5: Report final status without automatic push or deployment**

Report changed files, focused tests, static checks, known environment-limited checks, and remind the user to run `./dev.sh` manually for service/browser/live acceptance. Do not stage, push, deploy, or start services automatically.
