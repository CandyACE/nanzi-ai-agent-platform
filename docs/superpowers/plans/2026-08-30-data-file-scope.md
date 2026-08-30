# 数据/文件范围修复实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让消息底部“数据 / 文件”按当前会话是否存在产出物决定是否可用，并让数据与文件查看统一支持“本会话全部 / 本次消息”过滤。

**Architecture:** 后端产物列表增加会话过滤参数；前端将消息入口统一打开 `MyArtifactsDrawer`，抽屉维护查看范围并把范围传给数据结果和文件列表。当前消息角标继续从当前消息/当前 trace 计算，会话范围只用于按钮可用性和列表过滤。

**Tech Stack:** FastAPI、Pydantic、Vue 3、TypeScript、pytest、vue-tsc。

---

### Task 1: 补齐文件接口的会话过滤

**Files:**
- Modify: `app/api/v1/endpoints/chat.py` 的 `list_artifacts`
- Modify: `frontend/src/api/artifact.ts` 的 `ArtifactListParams`
- Modify: `frontend/src/components/embed/MyArtifactsDrawer.vue` 的文件加载请求
- Test: `tests/api/v1/test_reusable_result_api.py`
- Test: `tests/frontend/test_reusable_result_contract.py`

- [ ] **Step 1: Write the failing contract assertions**

断言后端存在 `conversation_id` 查询参数并将其加入查询过滤，前端请求类型和文件请求均传递 `conversation_id`；断言带当前消息范围时额外传递 `trace_id`。

- [ ] **Step 2: Run focused tests and verify they fail**

Run:
`python3 -m pytest tests/api/v1/test_reusable_result_api.py tests/frontend/test_reusable_result_contract.py -q`

Expected: FAIL because the artifact endpoint and file list request do not expose/use `conversation_id`.

- [ ] **Step 3: Implement the smallest API change**

在 `list_artifacts` 增加 `conversation_id: Optional[str] = Query(None)`，将 `AiArtifact.conversation_id == conversation_id` 加入已有 `filters`；在 `ArtifactListParams` 增加 `conversation_id?: string`；抽屉请求统一传 `conversation_id: props.conversationId || undefined`，当前消息范围再传 `trace_id: props.traceId || undefined`。

- [ ] **Step 4: Run focused tests and verify they pass**

同 Step 2，Expected: PASS。

### Task 2: 统一抽屉的“本会话全部 / 本次消息”范围

**Files:**
- Modify: `frontend/src/components/embed/MyArtifactsDrawer.vue`
- Modify: `frontend/src/components/embed/ReusableResultList.vue`
- Test: `tests/frontend/test_reusable_result_contract.py`

- [ ] **Step 1: Write the failing contract assertions**

增加对 `outputScope: 'conversation' | 'message'`、默认 `conversation`、文件和可复用结果共用范围开关、以及 `只看本次` / `查看本会话全部` 文案的断言。

- [ ] **Step 2: Run the focused test and verify it fails**

Run:
`python3 -m pytest tests/frontend/test_reusable_result_contract.py::test_reusable_result_details_are_limited_to_the_current_message_round tests/frontend/test_reusable_result_contract.py::test_artifacts_drawer_has_files_and_reusable_result_tabs -q`

Expected: FAIL because the current reusable列表只支持本轮/本次，文件列表没有范围开关。

- [ ] **Step 3: Implement the scope state**

在 `MyArtifactsDrawer.vue` 增加 `outputScope`，打开抽屉时默认设为 `conversation`；当 `traceId` 存在时显示范围切换，切换到 `message` 重新加载文件，并把范围传给 `ReusableResultList`。

在 `ReusableResultList.vue` 增加 `scope?: 'conversation' | 'message'`，默认 `conversation`；`conversation` 显示接口返回的会话列表，`message` 按 `trace_id === props.traceId` 过滤；当前结果继续用 `focusedResultId` 显示“本次生成/本次复用”标记。范围切换始终可见，不再依赖结果数量大于 1。

在文件列表区域增加同样的范围切换，文件请求使用：
`{ conversation_id: props.conversationId || undefined, trace_id: outputScope === 'message' ? props.traceId || undefined : undefined }`。

- [ ] **Step 4: Run focused tests and verify they pass**

Expected: PASS，且两个 tab 使用同一范围状态。

### Task 3: 让消息入口按会话产出物启用，并统一打开抽屉

**Files:**
- Modify: `frontend/src/components/chat/MessageActionMenus.vue`
- Modify: `frontend/src/views/EmbedChat.vue`
- Modify: `tests/frontend/test_reusable_result_contract.py`

- [ ] **Step 1: Write the failing contract assertions**

断言组件使用 `hasConversationDataFile`，EmbedChat 从 `artifactCountByTrace` 和全部消息状态计算会话级可用性；断言消息的“查看文件产物”也调用统一的 `MyArtifactsDrawer`，并能传当前消息 `trace_id`。

- [ ] **Step 2: Run focused tests and verify they fail**

Run:
`python3 -m pytest tests/frontend/test_reusable_result_contract.py::test_message_action_menus_group_data_file_and_low_frequency_actions tests/frontend/test_reusable_result_contract.py::test_embed_chat_wires_status_event_selection_and_one_shot_request_id -q`

Expected: FAIL because当前禁用条件仍按单个 trace 判断，文件入口仍打开独立的单消息文件抽屉。

- [ ] **Step 3: Implement the smallest state-flow change**

在 `MessageActionMenus.vue` 将 `hasRoundDataFile` 改为 `hasConversationDataFile`，按钮可用性只取该会话级布尔值；角标继续使用当前消息 `reusableCount` 和当前 trace 的 `artifactCount`。

在 `EmbedChat.vue` 增加：
`const hasConversationDataFile = computed(() => Object.values(artifactCountByTrace.value).some((count) => count > 0) || messages.value.some((msg) => Boolean(msg.hasDataOutput) || currentMessageReusableCount(msg) > 0));`

消息操作区传递 `:has-conversation-data-file="hasConversationDataFile"`。增加 `openMessageArtifacts(traceId)`，设置 `myArtifactsInitialTab = 'files'`、设置抽屉 `traceId` 并打开 `MyArtifactsDrawer`；“查看文件产物”改为调用该方法。普通“我的产出”入口清空 trace，默认显示本会话全部。

- [ ] **Step 4: Run focused tests and verify they pass**

Expected: PASS；前一条消息有产出时，后一条消息仍可点击“数据 / 文件”，且数字不被会话总量污染。

### Task 4: 全量验证并复核范围边界

**Files:**
- Verify: `app/api/v1/endpoints/chat.py`
- Verify: `frontend/src/api/artifact.ts`
- Verify: `frontend/src/components/chat/MessageActionMenus.vue`
- Verify: `frontend/src/components/embed/MyArtifactsDrawer.vue`
- Verify: `frontend/src/components/embed/ReusableResultList.vue`
- Verify: `frontend/src/views/EmbedChat.vue`

- [ ] **Step 1: Run regression tests**

Run:
`python3 -m pytest tests/api/v1/test_reusable_result_api.py tests/frontend/test_reusable_result_contract.py tests/frontend/test_general_message_continue_analysis_contract.py tests/frontend/test_chatbi_delivery_actions_contract.py -q`

Expected: all tests pass.

- [ ] **Step 2: Run frontend type checking**

Run:
`cd frontend && ./node_modules/.bin/vue-tsc --noEmit`

Expected: exit code 0.

- [ ] **Step 3: Check the diff**

Run:
`git diff --check`

Expected: no whitespace errors. Do not stage or commit unless explicitly requested.
