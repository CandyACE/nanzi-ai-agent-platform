# Audit Trace Payload Bounding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bound persisted and rendered execution-trace payloads without changing the tool result consumed by the AI runtime.

**Architecture:** Keep runtime `AgentExecutionStep.tool_output` unchanged. At audit persistence and response boundaries, create a JSON-safe bounded copy with a configurable byte limit and metadata describing original size and truncation. Keep complete structured results in the existing session result cache for export/notification consumers, return only bounded payloads from trace APIs, and make the viewer collapsed-by-default for large result bodies.

**Tech Stack:** Python 3.11, Pydantic 2, SQLAlchemy JSON, FastAPI, Vue 3 + TypeScript.

---

### Task 1: Add audit-payload bounding helper and regression tests

**Files:**
- Create: `app/services/ai/audit_payload.py`
- Test: `tests/services/ai/test_audit_payload.py`

- [x] **Step 1: Write failing tests** for preserving small JSON values, truncating large strings by UTF-8 bytes, preserving shape metadata, and proving the original object is not mutated.
- [x] **Step 2: Run the focused tests and verify they fail** because the helper does not exist.
- [x] **Step 3: Implement the minimal pure helper** with a 64 KiB default per payload and explicit `__audit` metadata.
- [x] **Step 4: Run the focused tests and verify they pass.**

### Task 2: Apply the bounded copy only when persisting Trace rows

**Files:**
- Modify: `app/services/ai/audit.py:130-164`
- Test: `tests/services/ai/test_audit_persistence_payload_contract.py`

- [x] **Step 1: Write a failing contract test** asserting `save_trace_logs` passes bounded output to the ORM while leaving the source `AgentExecutionStep` unchanged.
- [x] **Step 2: Run the focused test and verify it fails.**
- [x] **Step 3: Wrap only `tool_input` and `tool_output` at the persistence boundary** and preserve the existing runtime trace path.
- [x] **Step 4: Run the focused persistence test and existing audit tests.**

### Task 3: Prevent large Trace responses and eager browser rendering

**Files:**
- Modify: `app/api/portal/endpoints/audit.py:207-269`
- Modify: `frontend/src/components/TraceLogViewer.vue:93-98`
- Test: `tests/api/portal/test_trace_payload_contract.py`

- [x] **Step 1: Add API contract coverage** for the truncation metadata and the absence of unbounded recursive response expansion.
- [x] **Step 2: Implement response-safe metadata and collapse output sections by default for large traces.**
- [x] **Step 3: Run backend contract tests and the frontend contract/type checks.**

### Task 4: Review the final diff and report validation boundaries

- [x] **Step 1: Run `git diff --check` and inspect all changed files.**
- [x] **Step 2: Request an independent code review of the uncommitted diff.**
- [x] **Step 3: Report tests passed, live service/browser checks not run, and no commit performed.**
