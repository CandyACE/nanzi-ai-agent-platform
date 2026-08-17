# TurnDecision 单轨路由 Implementation Plan

> **完成记录：** 本文记录 2026-08-17 已实施的单轨路由改造。复选框反映实现与验证状态；服务启动、数据库迁移和代码提交不属于本次改造本身。

**实施状态：** 核心单轨路由已完成。旧通用分类器、旧会话 tuple、旧 route-hints 恢复协议和旧 replay fixture 已删除；剩余服务级测试需要本地 MySQL/Redis，未在本次验证中启动基础设施。

**本次验证：** 138 个单轨路由、回放、Dispatcher、Router、Grounding、ChatBI 内部分类、Prompt、工具策略和子代理测试通过；AST 解析、生产代码旧符号检查、聚焦 Ruff 和 `git diff --check` 通过。pytest 仅报告因沙箱目录权限无法写入 `.pytest_cache` 的 warning。

**文档同步：** 当前运行契约见 `docs/md/ai_agent_gating_contract.md` 和 `docs/md/api_integration_guide.md`；历史日期方案中的旧符号只描述当时的实现，不代表当前运行时协议。当前协议以 `TurnDecision` 单轨设计为准。

原计划中“确认失败”的步骤属于实施前的红阶段描述；本记录只把对应契约和迁移结果标记为完成，实际执行过的验证以本文件顶部和 Task 8 的记录为准。

**Goal:** Remove the legacy runtime routing path so `TurnDecision` is the only outer-turn decision passed from routing to execution, while retaining AgentScope, ChatBI's internal classifier, and all existing permission gates.

**Architecture:** Make `RouterService` return `TurnDecision` directly and add `turn_kind`/`route_status` to that model. Replace dictionary `route_hints`, `shared_turn`, and generic `TurnClassification` usage with typed decisions. Keep `RequestDecision` only as a non-persisted authorization view at permission boundaries until those APIs accept `TurnDecision` directly; it must not select an agent or executor.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic 2, AgentScope 2.x, pytest, existing SSE/runtime events.

---

## Task 1: Establish the single decision contract

**Files:**
- Modify: `app/services/ai/turn_decision.py`
- Test: `tests/ai/test_turn_decision.py`
- Test: `tests/ai/test_turn_decision_replay.py`

- [x] **Step 1: Write failing contract tests.** Add tests that require `TurnDecision` to expose `turn_kind` and `route_status`, construct direct selection through `TurnDecision.for_direct_agent_selection(...)`, and reject data execution when `route_status` is `failed` or `unknown`.

- [x] **Step 2: Run the focused tests and confirm the intended failure.**

  Run:

  ```sh
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. pytest -q tests/ai/test_turn_decision.py tests/ai/test_turn_decision_replay.py
  ```

  Expected: the new fields/factory are missing or the fail-closed assertion fails.

- [x] **Step 3: Implement the canonical fields and factories.** Add `turn_kind` and `route_status` with safe defaults, add `for_direct_agent_selection`, and replace adapter-only construction with explicit constructors usable by RouterService. Preserve `trace_payload`, but remove `from_route_result`, `to_route_hints`, `from_route_hints`, and `is_reusable_for_turn_classification` after all consumers have migrated.

- [x] **Step 4: Run the contract tests.**

  Run the command from Step 2. Expected: PASS.

## Task 2: Make RouterService the only outer router

**Files:**
- Modify: `app/services/ai/router_service.py`
- Modify: `app/services/ai/request_decision.py` only if an authorization-view signature requires it
- Modify: `tests/services/ai/test_router_service.py`
- Modify: `tests/ai/test_router_context.py`

- [x] **Step 1: Rewrite router tests to assert `TurnDecision`.** Replace `RouteResult` construction/assertions with checks for `agent_id`, `capability`, `turn_kind`, `route_status`, semantic evidence, secondary agents, and fail-closed `allows_data_route`.

- [x] **Step 2: Run the router tests and confirm they fail against the old return type.**

  ```sh
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. pytest -q tests/services/ai/test_router_service.py tests/ai/test_router_context.py
  ```

  Expected: assertions fail because the router still returns `RouteResult`.

- [x] **Step 3: Change RouterService's route result construction.** Replace every `RouteResult(...)` return with `TurnDecision(...)`; copy request source/capability, semantic fields, ChatBI qualification, dataset matches, confidence, provenance, and stage timings into the decision. Keep heuristic fast paths and permission qualification unchanged. Delete the `RouteResult` model and its imports.

- [x] **Step 4: Run router tests and fail-closed tests.** Expected: all focused router tests pass.

## Task 3: Remove AgentService and Dispatcher legacy classification

**Files:**
- Modify: `app/services/ai/agent_service.py`
- Modify: `app/services/ai/dispatcher.py`
- Delete: `app/services/ai/turn_classifier.py`
- Modify: `tests/ai/test_dispatcher_data_executor_boundary.py`
- Modify: `tests/ai/test_multi_agent_orchestrator.py`
- Modify: `tests/services/ai/test_agent_service_skill_hint.py`

- [x] **Step 1: Add failing tests for the single dispatch input.** Assert that `AgentDispatcher.dispatch()` accepts only a typed `TurnDecision`, that a general/knowledge/data decision selects the corresponding executor, and that no test can pass `shared_turn` or make Dispatcher call `resolve_turn_for_session`.

- [x] **Step 2: Run the dispatcher tests and confirm the old API still violates the contract.**

  ```sh
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. pytest -q tests/ai/test_dispatcher_data_executor_boundary.py tests/ai/test_multi_agent_orchestrator.py
  ```

- [x] **Step 3: Migrate AgentService.** Remove `resolve_turn_for_session`, `session_turn`, `shared_turn`, and the decision-reuse predicate. Use `TurnDecision.turn_kind` for outer logging and Executor selection. Direct Agent selection must call `TurnDecision.for_direct_agent_selection`; router failures must carry `route_status=failed` and stop before data/knowledge execution.

- [x] **Step 4: Migrate Dispatcher.** Remove `shared_turn`, `route_hints`, and its generic classification branches. Require `turn_decision`, validate its route status, and select the executor from `turn_kind`/capability. Keep ChatBI's internal classifier inside `DataQueryExecutor`.

- [x] **Step 5: Remove the generic classifier.** Delete `TurnClassification`, `resolve_turn_for_session`, `classify_turn_from_decision`, and related adapter-only helpers. Keep only classification utilities still used by ChatBI-specific code or UI labels, and update those call sites to read the decision directly.

- [x] **Step 6: Run the dispatcher and AgentService tests.** Expected: single-decision tests pass; no generic intent LLM is called by AgentService or Dispatcher.

## Task 4: Replace runtime route_hints with typed decisions

**Files:**
- Modify: `app/services/ai/executors/assistant_executor.py`
- Modify: `app/services/ai/executors/data_executor.py`
- Modify: `app/services/ai/executors/knowledge_executor.py`
- Modify: `app/services/ai/runners/assistant_agent_runner.py`
- Modify: `app/services/ai/runners/data_agent_runner.py`
- Modify: `app/services/ai/runners/knowledge_agent_runner.py`
- Modify: `app/services/ai/runners/chatbi/handoff.py`
- Modify: `app/services/ai/runners/chatbi/system_prompt.py`
- Modify: related executor and runner tests

- [x] **Step 1: Add typed-constructor tests.** Instantiate each executor/runner with `turn_decision=TurnDecision(...)` and assert the decision reaches grounding, tool preflight, ChatBI handoff, and system-prompt construction. Add a test that a plain `route_hints` dictionary is rejected or ignored.

- [x] **Step 2: Run those tests and confirm the old constructors do not satisfy them.**

- [x] **Step 3: Change constructors and state.** Replace `route_hints` parameters and fields with `turn_decision: TurnDecision`. For persisted current-state records, serialize only `TurnDecision.model_dump(mode="json")` under the new current-state field and validate it on restore. Do not read old route-hints fields.

- [x] **Step 4: Update prompt, grounding, tool-preflight, and ChatBI handoff consumers.** Remove dictionary fallback reads and use explicit decision properties. Keep permission checks after decision interpretation.

- [x] **Step 5: Run focused executor/runner tests.** Expected: all typed-decision tests pass and no production route-hints reference remains.

## Task 5: Keep ChatBI domain classification inside DataQueryExecutor

**Files:**
- Modify: `app/services/ai/executors/data_executor.py`
- Modify: `app/services/ai/runners/data_agent_runner.py`
- Modify: `app/services/ai/data_query_turn_classifier.py` only for typed decision input
- Keep: `app/services/ai/runners/chatbi/repair_controller.py`
- Test: ChatBI executor, turn-classifier, repair, SQL result, and synthesis tests

- [x] **Step 1: Add tests proving outer routing and inner ChatBI classification are separate.** A `TurnDecision(turn_kind="data_query")` must select `DataQueryExecutor`; the executor must still classify new query/follow-up/result-reuse internally.

- [x] **Step 2: Run the tests and confirm the new outer contract fails before migration.**

- [x] **Step 3: Pass the typed decision into DataQueryExecutor and its runner.** Do not turn `DataQueryTurnType` into a second outer route. Preserve SQL/schema gates, repair controller, successful-SQL synthesis rescue, and AgentScope event flow.

- [x] **Step 4: Run ChatBI focused tests.** Expected: ChatBI domain behavior remains green.

## Task 6: Migrate tools, prompt, subagents, and trace

**Files:**
- Modify: `app/services/ai/prompt_assembler.py`
- Modify: `app/services/ai/agent_prompts.py`
- Modify: `app/services/ai/tool_nudge_policy.py`
- Modify: `app/services/ai/tools/agent_delegate_tool.py`
- Modify: `app/services/ai/subagent_protocol.py`
- Modify: `app/services/ai/turn_decision.py`
- Test: prompt, tool policy, subagent, and trace tests

- [x] **Step 1: Add failing tests for direct typed consumption.** Assert prompt assembly, tool nudge, subagent capability metadata, and trace all consume the same `TurnDecision` object and do not reconstruct route decisions from dictionaries.

- [x] **Step 2: Migrate consumers.** Remove route-hints adapters, pass the typed object directly, and keep metadata/permission semantics unchanged.

- [x] **Step 3: Run focused prompt/tool/subagent tests.** Expected: all pass.

## Task 7: Delete legacy symbols and old test contracts

**Files:**
- Modify: `tests/ai/test_turn_decision.py`, `tests/ai/test_router_context.py`, `tests/services/ai/test_router_service.py`
- Delete: `tests/ai/test_turn_classifier.py` and old route-hints fixtures
- Add: `tests/ai/fixtures/turn_decision_cases.json`, `tests/ai/test_turn_decision_replay.py`, `tests/ai/test_single_track_routing_contract.py`

- [x] **Step 1: Add a static forbidden-symbol test.** It must scan production Python files and fail if any of `RouteResult`, `shared_turn`, `resolve_turn_for_session`, or `route_hints` appears in runtime code.

- [x] **Step 2: Delete adapter-only code and old fixtures.** Remove compatibility methods and tests that only exercise old route-hints or shared-turn behavior. Keep ChatBI-specific names that contain “turn” but do not represent outer routing.

- [x] **Step 3: Run the static contract test and repository symbol search.** Expected: no forbidden runtime symbol remains.

## Task 8: Full focused verification and documentation

**Files:**
- Modify: `docs/superpowers/specs/2026-08-17-turn-decision-single-track-design.md`
- Modify: this plan with executed results
- Modify: `tests/CHECKLIST.md` only if the repository checklist requires a new entry

- [x] **Step 1: Run the focused suite.**

  ```sh
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. pytest -q \
    tests/services/ai/test_router_service.py \
    tests/ai/test_router_context.py \
    tests/ai/test_single_track_routing_contract.py \
    tests/ai/test_dispatcher_data_executor_boundary.py \
    tests/ai/test_prompt_assembler.py \
    tests/ai/test_tool_nudge_policy.py \
    tests/ai/test_sub_agent_delegation.py \
    tests/ai/runners/test_chatbi_repair_controller.py \
    tests/ai/runners/test_chatbi_modules.py
  ```

- [x] **Step 2: Run syntax and hygiene checks.** Use AST parsing without writing `.pyc`, `git diff --check`, and the focused Ruff command for newly created modules. Record any unrelated baseline failures separately.

- [x] **Step 3: Update the plan with exact results.** Do not claim the full suite or service-level integration unless it was actually run.

No service startup, database migration, staging, or commit is part of this plan.
