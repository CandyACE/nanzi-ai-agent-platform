# Grounding Evidence Contract Implementation Plan

> For agentic workers: use task-by-task execution with the repository's TDD workflow. Steps use checkbox syntax for tracking.

Goal: Decouple request-source classification from grounding evidence requirements so unknown or conflicting ordinary requests do not receive false risk warnings while explicit high-risk evidence requirements remain protected.

Architecture: Add a small evidence-contract normalization boundary under app/services/ai/grounding, convert the contract into the existing FactRequirement, and keep explicit retry/method actions in the runner as the highest-priority override. Route and grounding logs expose the normalized origin and conflicts without changing the user-facing warning format.

Tech Stack: Python, dataclasses/enums, pytest, existing EvidenceLedger, RequestDecision, GroundingService, and AgentScope SSE log payloads.

---

### Task 1: Add failing contract and policy tests

Files:

- Create: app/services/ai/grounding/contract.py
- Modify: tests/ai/grounding/test_grounding_policy.py
- Modify: tests/ai/runners/test_assistant_agent_grounding_gate.py

- [ ] Step 1: Add a test that unknown requests do not require evidence.

Use a RequestDecision with source UNKNOWN and capability ANSWER. Assert that resolve_fact_requirement returns required=False, scrutinize_unknown_output=False, and an empty accepted_types set.

- [ ] Step 2: Add a test that unknown public-web metadata records a conflict without requiring evidence.

Use source UNKNOWN with semantic_domain public_web and fact_kind public_fact. Assert required=False and a decision_conflicts entry explaining the unknown-source conflict.

- [ ] Step 3: Add a test that explicit public-web source still requires public evidence.

Use source PUBLIC_WEB and capability WEB_SEARCH. Assert required=True and accepted_types containing PUBLIC_WEB.

- [ ] Step 4: Add a runner-level failing regression for a date answer.

Configure an AssistantAgentRunner with grounding enabled and request_source UNKNOWN. Stream the answer “今天是 2026年7月30日，星期四。” from a fake core. Assert that no grounding warning is emitted.

- [ ] Step 5: Run the focused tests and verify they fail for the current implementation.

Run:

    venv/bin/python -m pytest tests/ai/grounding/test_grounding_policy.py -k "unknown_request or unknown_public_web or explicit_public_web" -q
    venv/bin/python -m pytest tests/ai/runners/test_assistant_agent_grounding_gate.py -k "date" -q

Expected: the new unknown tests fail because the current policy scrutinizes unknown output and allows semantic evidence fields to populate accepted_types.

### Task 2: Implement the evidence-contract normalization boundary

Files:

- Create: app/services/ai/grounding/contract.py
- Modify: app/services/ai/grounding/policy.py in FactRequirement and resolve_fact_requirement
- Modify: app/services/ai/runners/assistant_agent_runner.py in request-decision and grounding-requirement resolution

- [ ] Step 1: Define EvidenceContractMode, EvidenceDecisionOrigin, and EvidenceContract.

Use immutable dataclasses. The contract must contain mode, accepted_types, origin, confidence, reason, and conflicts.

- [ ] Step 2: Extend FactRequirement with defaulted diagnostic metadata.

Add decision_origin, decision_confidence, and decision_conflicts with safe defaults so existing constructors and callers remain compatible.

- [ ] Step 3: Normalize unknown decisions.

When the effective source is UNKNOWN and there is no explicit retry/method action, return an optional, non-required requirement with no accepted evidence types. Detect and retain conflicts for semantic domains or fact kinds that would otherwise map to public web, runtime, internal data, knowledge, or user-file evidence. Preserve optional unknown-output scrutiny for unresolved structured facts so existing business-data protection is not weakened.

- [ ] Step 4: Preserve explicit and high-confidence requirements.

Keep source mappings for PUBLIC_WEB, RUNTIME_DIAGNOSTIC, INTERNAL_STRUCTURED_DATA, and INTERNAL_DOCS. Keep the existing high-confidence DATA_QUERY and KNOWLEDGE_BASE source upgrades in the runner. Do not let a weak domain or fact_kind alone upgrade UNKNOWN.

- [ ] Step 5: Re-run deterministic boundaries before accepting UNKNOWN.

In AssistantAgentRunner, call resolve_request_decision(user_query) when the route source is UNKNOWN or GENERAL. Return the inferred deterministic decision when it moves the query to a non-UNKNOWN source, so dates, greetings, runtime diagnostics, and public-fact lexical boundaries do not inherit stale route metadata.

- [ ] Step 6: Preserve explicit grounding actions.

Keep grounding_action type method and typed retry handling ahead of automatic contract normalization.

- [ ] Step 7: Run the focused red-green tests.

Run:

    venv/bin/python -m pytest tests/ai/grounding/test_grounding_policy.py -k "unknown_request or unknown_public_web or explicit_public_web" tests/ai/runners/test_assistant_agent_grounding_gate.py -k "date" -q

Expected: the new tests pass and explicit evidence-required behavior remains green.

### Task 3: Add structured decision observability

Files:

- Modify: app/services/ai/runners/assistant_agent_runner.py in grounding warning log construction
- Modify: app/services/ai/agent_service.py in router_log construction
- Modify: tests/ai/runners/test_assistant_agent_grounding_gate.py

- [ ] Step 1: Add failing assertions for diagnostic metadata.

Assert that a grounding log contains decision_origin, decision_confidence, evidence_mode, and decision_conflicts when a normalized requirement is used. Assert that the ordinary unknown date path has no warning log.

- [ ] Step 2: Add normalized metadata to grounding log events.

Keep the existing user-facing details text and add a structured grounding_decision object to internal log events.

- [ ] Step 3: Add normalized metadata to router log events.

Preserve all existing route fields and add empty/default values for legacy shortcut routes that have no RequestDecision.

- [ ] Step 4: Run the focused observability tests.

Run:

    venv/bin/python -m pytest tests/ai/runners/test_assistant_agent_grounding_gate.py -k "grounding_decision or date" -q

Expected: structured metadata is present for grounding decisions and unknown ordinary answers remain warning-free.

### Task 4: Complete regression coverage and validation

Files:

- Modify: tests/ai/grounding/test_grounding_policy.py
- Modify: tests/ai/grounding/test_grounding_service.py
- Modify: tests/ai/test_request_decision.py
- Modify: tests/ai/test_turn_classifier.py
- Modify: tests/CHECKLIST.md

- [ ] Step 1: Add the decision matrix.

Cover unknown dynamic answers, unknown high-risk business tables, explicit public web with and without evidence, explicit internal data with and without evidence, runtime state, knowledge retrieval, conversation reuse, and retry/method overrides.

- [ ] Step 2: Run the complete targeted AI regression slice.

Run:

    venv/bin/python -m pytest tests/ai/grounding tests/ai/test_request_decision.py tests/ai/test_turn_classifier.py tests/ai/runners/test_assistant_agent_grounding_gate.py -q

Expected: all targeted tests pass. Report unrelated baseline failures separately if any appear outside this change.

- [ ] Step 3: Run syntax and whitespace checks.

Run:

    venv/bin/python -m compileall -q app/services/ai/grounding app/services/ai/runners/assistant_agent_runner.py
    git diff --check

Expected: both commands exit successfully.

- [ ] Step 4: Update tests/CHECKLIST.md.

Add a row describing the evidence-contract boundary, unknown/conflict behavior, explicit evidence preservation, and the focused test command. Do not claim full-suite or live-runtime validation.

- [ ] Step 5: Inspect the final diff and leave changes uncommitted.

Run:

    git status --short
    git diff --stat
    git diff --check

Expected: only the design/plan documents, grounding implementation, focused tests, and checklist are changed; no service is started and no commit is created automatically.
