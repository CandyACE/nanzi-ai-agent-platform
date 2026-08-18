# Knowledge Catalog Gating Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use `test-driven-development` and execute each task in order.

**Goal:** 让知识库权限目录参与知识库路由门控，避免通用“政策/查询”信号强制知识库子代理；无高置信目录匹配时允许一次直接检索兜底。

**Architecture:** 提取共享的授权知识库目录读取层，供提示词摘要、路由门控和 `list_accessible_knowledge_bases` 使用；在 `RequestDecision`/`TurnDecision` 中传递目录匹配证据与一次性兜底标志；保留工具层权限校验作为最终边界。

**Tech stack:** Python 3.11, pytest, FastAPI/AgentScope existing services.

## Task 1: Add failing routing and catalog contract tests

**Files:**
- Modify: `tests/ai/test_request_decision.py`
- Modify: `tests/ai/test_accessible_resource_catalog.py`
- Modify: `tests/ai/tools/test_resource_catalog_tools.py`
- Modify: `tests/ai/test_tool_nudge_policy.py`

**Steps:**
1. Add a regression for a generic public/factual query containing a knowledge signal: it must not produce a strong knowledge route or force delegation, while preserving one-time fallback eligibility when an effective catalog exists.
2. Add a metadata-match case proving a semantically related authorized catalog item still produces the normal knowledge route.
3. Add empty/unavailable catalog cases proving search is disallowed without effective permission and that unavailable is not reported as no match.
4. Add an explicit dataset-selection case proving explicit scope overrides catalog matching.
5. Add a tool-nudge case proving weak catalog evidence cannot force `sub_agent_call`.
6. Run the focused tests and confirm RED before production changes.

## Task 2: Implement shared authorized catalog and generic match evidence

**Files:**
- Add: `app/services/ai/knowledge_catalog.py`
- Modify: `app/services/ai/accessible_resource_catalog.py`
- Modify: `app/services/ai/tools/resource_catalog_tools.py`
- Modify: `app/services/ai/request_decision.py`
- Modify: `app/services/ai/router_service.py`
- Modify: `app/services/ai/turn_decision.py`

**Steps:**
1. Centralize full authorized knowledge-base metadata loading with explicit `available`/`empty`/`unavailable` status.
2. Add domain-agnostic metadata normalization and relevance scoring over name/description/tags/notes, returning matched IDs and confidence tier.
3. Make prompt summary and list tool consume the shared authorized catalog without exposing unbounded prompt text.
4. Make `_KNOWLEDGE_SIGNALS` a candidate signal only; require strong catalog evidence or explicit scope for normal knowledge delegation.
5. Carry weak/no-match fallback eligibility through the request/turn decision without expanding permission scope.
6. Ensure router-provided strong internal-doc intent remains compatible with catalog evidence and does not turn generic weak evidence into sub-agent delegation.

## Task 3: Enforce one-time direct-search fallback and prevent forced delegation

**Files:**
- Modify: `app/services/ai/runners/knowledge_agent_runner.py`
- Modify: `app/services/ai/assistant_agent_runner.py`
- Modify: `app/services/ai/tool_nudge_policy.py`
- Add/Modify: relevant tests under `tests/ai/runners/` and `tests/ai/`

**Steps:**
1. Allow a weak/no-match candidate to perform at most one direct `search_knowledge_base` attempt when effective dataset IDs exist.
2. Prevent the fallback marker from causing automatic knowledge sub-agent delegation.
3. Preserve existing explicit selection and tool-level permission behavior.
4. Add a regression proving a second search or sub-agent nudge is rejected/skipped after the first fallback.

## Task 4: Verify and audit

**Files:**
- No production file changes expected.

**Steps:**
1. Run the focused routing/catalog/nudge/knowledge-runner tests.
2. Run the broader existing AI routing and resource-catalog suites.
3. Run `python -m compileall` on changed Python modules and `git diff --check` on the scoped diff.
4. Inspect `git status` and report only files changed for this request; do not stage or commit.
