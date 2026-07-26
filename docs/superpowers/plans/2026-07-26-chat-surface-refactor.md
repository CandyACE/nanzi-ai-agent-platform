# Chat Surface Refactor Implementation Plan

> **For agentic workers:** Execute this plan task-by-task with tests before implementation and keep each extraction independently reviewable.

**Goal:** Split the two oversized chat views along safe responsibility boundaries while preserving all current behavior.

**Architecture:** Keep `EmbedChat.vue` and `AgentDebug.vue` as orchestration shells. Move pure dialogs and repeated presentation first; move shared stream/citation/resource logic only after focused contracts cover the existing behavior. Keep mode-specific request construction and event handling separate until their differences are explicit.

**Tech Stack:** Vue 3 `<script setup>` with TypeScript, existing Python frontend contract tests, Vue SFCs, existing SSE parser and composables.

---

### Task 1: Extract AgentDebug logic-flow dialog

**Files:**
- Create: `frontend/src/components/debug/AgentLogicFlowModal.vue`
- Modify: `frontend/src/views/AgentDebug.vue`
- Test: `tests/frontend/test_chat_surface_extraction_contract.py`

- [ ] Add a failing contract requiring the parent to use `AgentLogicFlowModal`, the child to expose `visible` and `close`, and the original SVG labels to remain present.
- [ ] Run the focused test and confirm it fails because the component does not exist yet.
- [ ] Move the existing dialog markup without changing SVG geometry, labels, classes, or close behavior.
- [ ] Replace the inline markup with `<AgentLogicFlowModal :visible="showLogicFlowModal" @close="showLogicFlowModal = false" />`.
- [ ] Run the focused test and the existing chat-surface contract tests.

### Task 2: Extract shared model-call statistics presentation

**Files:**
- Create: `frontend/src/components/chat/ChatModelCallStatsModal.vue`
- Modify: `frontend/src/views/EmbedChat.vue`
- Modify: `frontend/src/views/AgentDebug.vue`
- Test: `tests/frontend/test_chat_surface_extraction_contract.py`

- [ ] Add a failing contract for the shared component props/events and removal of both inline stats modal markers.
- [ ] Implement the component with typed `visible`, `loading`, `stats`, and `expanded` inputs plus `close` and `toggle` events.
- [ ] Preserve the existing summary, tool-call, reasoning, output, empty, and loading states.
- [ ] Replace both inline blocks while leaving each page's data-loading function and state ownership unchanged.
- [ ] Run focused and existing frontend contracts.

### Task 3: Extract saved-report editor and run dialogs

**Files:**
- Create: `frontend/src/components/chat/SavedReportEditorModal.vue`
- Create: `frontend/src/components/chat/SavedReportRunModal.vue`
- Modify: `frontend/src/views/EmbedChat.vue`
- Modify: `frontend/src/views/AgentDebug.vue`
- Test: `tests/frontend/test_chat_surface_extraction_contract.py`

- [ ] Add contracts for both views using the two shared dialogs and retaining submit/preview/execute event wiring.
- [ ] Move only template presentation; keep form refs, preview scheduling, save, and execute functions in the pages initially.
- [ ] Preserve `Teleport`, overlay placement, loading/disabled states, date/month range fields, permission preview, and existing event payloads.
- [ ] Run saved-report and ChatBI delivery contracts plus the full focused frontend slice.

### Task 4: Extract lower-level stream and citation helpers

**Files:**
- Create: `frontend/src/utils/sseJsonStream.ts`
- Create: `frontend/src/composables/chat/useChatCitations.ts`
- Modify: `frontend/src/views/EmbedChat.vue`
- Modify: `frontend/src/views/AgentDebug.vue`
- Test: `tests/frontend/test_chat_shared_helpers_behavior.py`

- [ ] Add behavior tests for chunk boundaries, `[DONE]`, flush, and malformed-event handling before implementing the helper.
- [ ] Implement only transport/parsing concerns; keep per-page event dispatch and request payload construction unchanged.
- [ ] Move citation popover state and target resolution behind a callback for page-specific original-document behavior.
- [ ] Run the focused shared-helper and chat-surface suites.

### Task 5: Extract Embed resource-scope workflow and presentation

**Files:**
- Create: `frontend/src/composables/chat/useResourceScope.ts`
- Create: `frontend/src/components/embed/SessionResourceScopeBar.vue`
- Create: `frontend/src/components/embed/ResourceScopeModal.vue`
- Modify: `frontend/src/views/EmbedChat.vue`
- Test: `tests/frontend/test_resource_scope_dataset_options_contract.py`

- [ ] Add contracts for loading, save, refresh, orphan selection, metadata dataset mounting, and session reset behavior.
- [ ] Move state transitions and persistence into the composable; preserve request sequencing guards.
- [ ] Move only the bar/modal template into components and keep `resourceScope` exposed to request construction.
- [ ] Run all resource-scope, dataset-menu, workspace-canvas, and chat-surface contracts.

### Task 6: Split message presentation after the safe slices are green

**Files:**
- Create: `frontend/src/components/chat/ChatMessageActions.vue`
- Create: `frontend/src/components/chat/ChatMessageAttachments.vue`
- Create: `frontend/src/components/chat/ChatThoughtTimeline.vue`
- Create: `frontend/src/components/chat/ChatCitationList.vue`
- Modify: `frontend/src/views/EmbedChat.vue`
- Modify: `frontend/src/views/AgentDebug.vue`
- Test: `tests/frontend/test_message_renderer_contract.py` and new focused contracts

- [ ] Define a shared base message/log type and retain Embed/Debug extension fields.
- [ ] Extract one presentation boundary at a time, keeping event payloads typed.
- [ ] Verify streaming updates, pending permission/external execution, citation clicks, quick questions, attachments, feedback, and saved-report actions after each boundary.
- [ ] Consider a full `ChatMessageList` only if the smaller components do not leave a giant wrapper.

