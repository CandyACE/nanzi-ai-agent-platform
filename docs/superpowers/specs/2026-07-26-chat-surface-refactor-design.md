# Chat Surface Refactor Design

## Goal

Reduce the maintenance risk of `EmbedChat.vue` and `AgentDebug.vue` without changing user-visible chat, streaming, permission, workspace, portal, saved-report, citation, or debug behavior.

## Constraints and invariants

- Do not change API endpoints, request payload semantics, SSE event ordering, or permission-confirmation behavior.
- Do not start `./dev.sh`.
- Preserve the existing Python frontend contract-test workflow and add a failing contract before each extraction slice.
- Keep Embed-specific host/auth/routing/resource-scope behavior separate from AgentDebug-specific prompt/debug/logic-flow behavior.
- Do not auto-stage or commit code.

## Architecture

Use thin page shells around focused shared components and composables. Begin with pure UI extractions that have no network or reactive-message dependencies. Extract shared runtime helpers only after those boundaries are covered by tests.

The first slice extracts the AgentDebug logic-flow dialog into `components/debug/AgentLogicFlowModal.vue`. The parent owns `showLogicFlowModal`; the child receives `visible` and emits only `close`. The SVG and explanatory copy remain unchanged.

Later slices may extract the duplicated model-call statistics dialog, saved-report editor/run dialogs, SSE response consumption, citation state, and Embed resource-scope workflow. The two message models should share a base type while retaining mode-specific extensions.

## Verification

- Run the new focused contract test first and observe the expected failure.
- Run it after extraction, then run the existing chat-surface, message-renderer, ChatBI, workspace-canvas, and saved-report contract tests.
- Run `git diff --check`.
- Run the frontend type check/build only if its existing baseline is available; report unrelated baseline failures separately.
