# 刷新模式事实接地门控 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让刷新模式只对未验证事实追加最高级别风险提示，放行拒答与澄清，并尽量避免标准路径产生阻断动作。

**Architecture:** 在现有 `evaluate_grounding` 内先识别候选回答是否包含事实信号；刷新模式下非事实回答直接通过，事实回答在证据不足时保留正文并返回高风险软提示。普通模式的既有低/中/高风险分层保持不变，runner、工具权限、证据账本和 API 不变。

**Tech Stack:** Python 3.11+, pytest, FastAPI/AgentScope grounding policy.

---

### Task 1: 固化刷新模式的候选回答边界

**Files:**
- Modify: `tests/ai/grounding/test_grounding_policy.py`
- Test: `tests/ai/grounding/test_grounding_policy.py`

- [x] **Step 1: Write failing tests for safe non-factual responses**

在现有策略测试中增加三个场景：陈旧证据、兼容内部证据、完全缺失证据；每个场景使用拒答或澄清文本，并断言刷新模式返回 `PASS` 与 `NONE` 风险。

```python
def test_fresh_stale_evidence_allows_refusal_without_warning():
    now = datetime.now(timezone.utc)
    ledger = EvidenceLedger(user_id="u1", conversation_id="c1")
    ledger.record_success(
        call_id="runtime-old",
        producer="list_process",
        evidence_types={EvidenceType.RUNTIME_STATE},
        result={"load": 0.2},
        observed_at=now - timedelta(seconds=31),
        freshness=FactFreshness.REALTIME,
    )
    decision = evaluate_grounding(
        requirement=FactRequirement(
            required=True,
            accepted_types=frozenset({EvidenceType.RUNTIME_STATE}),
            freshness=FactFreshness.REALTIME,
            max_age_seconds=30,
            block_unsupported_facts=True,
        ),
        candidate_text="我暂时无法读取运行状态，请稍后重试。",
        ledger=ledger,
    )
    assert decision.action == GroundingAction.PASS
    assert decision.risk_level == GroundingRiskLevel.NONE
```

- [x] **Step 2: Run the focused test and verify it fails for the current implementation**

Run: `./.venv/bin/python -m pytest --confcutdir=tests/ai tests/ai/grounding/test_grounding_policy.py -k "fresh_stale_evidence_allows_refusal"`

Expected: FAIL because the current stale-evidence branch returns `BLOCK_UNGROUNDED_FACTS`.

- [x] **Step 3: Add factual fresh-mode warning expectations**

为陈旧、内部兼容、缺失和“证据存在但内容不相关”四类刷新事实回答增加断言：动作是 `GroundingAction.PASS_WITH_WARNING`，风险是 `GroundingRiskLevel.HIGH`，正文仍由上层保留。

- [x] **Step 4: Run the focused policy tests and verify the new tests fail before implementation**

Run: `./.venv/bin/python -m pytest --confcutdir=tests/ai tests/ai/grounding/test_grounding_policy.py -k "fresh or stale or internal_data or evidence"`

Expected: the newly added assertions expose the current unconditional block behavior.

### Task 2: Implement warning-first grounding policy

**Files:**
- Modify: `app/services/ai/grounding/policy.py:573-715`

- [x] **Step 1: Add the safe-response gate**

在 `evaluate_grounding` 计算 `text` 后，增加仅针对 `requirement.block_unsupported_facts` 的事实门控：未命中 `_contains_structural_external_fact(text)` 的候选回答直接返回 `PASS/NONE`。这样不会改变普通模式的既有 warning 分层。

- [x] **Step 2: Convert standard fresh-mode blocks to high warnings**

将刷新模式下“证据为空/不相关、陈旧证据、内部兼容证据和缺失证据”的 `BLOCK_UNGROUNDED_FACTS` 改为 `PASS_WITH_WARNING`，并固定 `GroundingRiskLevel.HIGH`；保留原有 reason、required types 和 available types 元数据。

- [x] **Step 3: Keep exact fresh evidence behavior unchanged**

新鲜且候选内容与证据收据相关时仍返回 `PASS`；明确无结果且没有事实信号的回答仍返回 `PASS`，不追加风险提示。

### Task 3: Update documentation and run regression checks

**Files:**
- Modify: `tests/CHECKLIST.md:402`
- Review: `docs/superpowers/specs/2026-08-22-grounding-fact-gate-design.md`

- [x] **Step 1: Rewrite the checklist entry**

将“无条件阻断”改为“刷新模式事实缺证据时保留回答并追加 HIGH 风险提示；拒答/澄清放行”，并明确当前 `BLOCK_UNGROUNDED_FACTS` 仅保留为兼容动作枚举，不是标准路径的硬拦截。

- [x] **Step 2: Run focused backend regression tests**

Run: `./.venv/bin/python -m pytest --confcutdir=tests/ai tests/ai/grounding/test_grounding_policy.py tests/ai/grounding/test_grounding_service.py`

Expected: all selected tests pass.

- [x] **Step 3: Run grounding runner tests and syntax checks**

Run: `./.venv/bin/python -m pytest --confcutdir=tests/ai tests/ai/runners/test_data_agent_runner.py -k grounding` and `./.venv/bin/python -m compileall -q app/services/ai/grounding`.

Expected: selected runner tests pass and compileall exits successfully.

- [x] **Step 4: Inspect final diff**

Run: `git diff --check` and `git status --short`.

Expected: no whitespace errors; only the intended policy, grounding tests, checklist, design, and plan files are changed or untracked.
